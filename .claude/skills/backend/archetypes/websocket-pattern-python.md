---
skill: websocket-pattern-python
description: Python WebSocket archetype — FastAPI WebSocket, Django Channels, connection manager, rooms, broadcasting, auth
version: "1.0"
tags:
  - python
  - websocket
  - fastapi
  - django-channels
  - real-time
  - archetype
  - backend
---

# WebSocket Pattern — Python

> **Canonical reference**: This is the Python counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): imported, type-checked, the ticket + WebSocket flow driven through TestClient and a real uvicorn server with a `websockets` 17.1 client (bad ticket → close 4001, cross-tenant room → FORBIDDEN), the Channels consumer run with WebsocketCommunicator, and RedisTicketStore run on Redis 7 (`run.sh --live`). FastAPI 0.142.2, uvicorn 0.54.0, channels 4.3.2, Django 6.1.1, redis 8.1.0.

Python WebSocket servers use FastAPI's built-in WebSocket support (backed by Starlette/uvicorn) or Django Channels for Django projects.

## Connection Manager

```python
# app/ws/manager.py

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    """Represents a single WebSocket client connection."""

    id: str
    user_id: str
    tenant_id: str
    roles: list[str]
    websocket: WebSocket
    rooms: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    """Manages all active WebSocket connections, rooms, and broadcasting."""

    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}
        self._rooms: dict[str, set[str]] = {}  # room_id -> set of conn_ids
        self._users: dict[str, set[str]] = {}  # user_id -> set of conn_ids
        self._lock = asyncio.Lock()

    async def register(self, conn: Connection) -> None:
        async with self._lock:
            self._connections[conn.id] = conn
            self._users.setdefault(conn.user_id, set()).add(conn.id)

        logger.info("ws.connected", extra={"conn_id": conn.id, "user_id": conn.user_id})

    async def unregister(self, conn: Connection) -> None:
        async with self._lock:
            self._connections.pop(conn.id, None)

            # Remove from user map
            if conn.user_id in self._users:
                self._users[conn.user_id].discard(conn.id)
                if not self._users[conn.user_id]:
                    del self._users[conn.user_id]

            # Remove from all rooms
            for room in list(conn.rooms):
                if room in self._rooms:
                    self._rooms[room].discard(conn.id)
                    if not self._rooms[room]:
                        del self._rooms[room]

        logger.info("ws.disconnected", extra={"conn_id": conn.id, "user_id": conn.user_id})

    async def subscribe(self, conn: Connection, room: str) -> None:
        async with self._lock:
            self._rooms.setdefault(room, set()).add(conn.id)
            conn.rooms.add(room)

        logger.info("ws.subscribed", extra={"conn_id": conn.id, "room": room})

    async def unsubscribe(self, conn: Connection, room: str) -> None:
        async with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(conn.id)
                if not self._rooms[room]:
                    del self._rooms[room]
            conn.rooms.discard(room)

        logger.info("ws.unsubscribed", extra={"conn_id": conn.id, "room": room})

    async def broadcast_to_room(
        self, room: str, message: dict[str, Any], except_conn_id: str | None = None,
    ) -> None:
        async with self._lock:
            conn_ids = list(self._rooms.get(room, set()))

        for conn_id in conn_ids:
            if conn_id == except_conn_id:
                continue
            conn = self._connections.get(conn_id)
            if conn:
                await self._safe_send(conn, message)

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            conn_ids = list(self._users.get(user_id, set()))

        for conn_id in conn_ids:
            conn = self._connections.get(conn_id)
            if conn:
                await self._safe_send(conn, message)

    async def _safe_send(self, conn: Connection, message: dict[str, Any]) -> None:
        try:
            await conn.websocket.send_json(message)
        except Exception:
            logger.debug("ws.send_failed", extra={"conn_id": conn.id})

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    @property
    def active_rooms(self) -> int:
        return len(self._rooms)


# Singleton instance
manager = ConnectionManager()
```

## Single-Use Connection Tickets

Browsers can't set an `Authorization` header on a WebSocket, and a bearer token in the URL lands in
proxy and access logs (`websocket-pattern.md` §Authentication on Upgrade). The client instead gets a
ticket from an authenticated `POST /api/v1/ws-tickets` and connects with `?ticket=`. A ticket lives
~30 s and works once: redeeming it is an atomic GET+DELETE, so a ticket seen in a log is already useless.

```python
# app/ws/tickets.py

import json
import secrets
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from starlette.requests import HTTPConnection

from app.dependencies.auth import CurrentUser, get_current_user  # auth-middleware-python.md
from app.middleware.request_id import get_request_id

TICKET_TTL_SECONDS = 30


@dataclass(frozen=True, slots=True)
class TicketClaims:
    """Who the ticket was issued to, copied from the verified token at issue time."""

    user_id: str
    tenant_id: str
    roles: tuple[str, ...]


class TicketStore(Protocol):
    async def issue(self, claims: TicketClaims) -> str: ...

    async def redeem(self, ticket: str) -> TicketClaims | None:
        """The ticket's claims, deleted in the same step; None when unknown, expired or already used."""
        ...


class RedisTicketStore:
    """Tickets in Redis (shared by every replica: the POST and the upgrade can hit different pods)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def issue(self, claims: TicketClaims) -> str:
        ticket = secrets.token_urlsafe(32)
        await self._redis.set(f"ws-ticket:{ticket}", json.dumps(asdict(claims)), ex=TICKET_TTL_SECONDS)
        return ticket

    async def redeem(self, ticket: str) -> TicketClaims | None:
        raw = await self._redis.getdel(f"ws-ticket:{ticket}")  # GETDEL (Redis >= 6.2): atomic, single use
        if raw is None:
            return None
        data = json.loads(raw)
        return TicketClaims(user_id=data["user_id"], tenant_id=data["tenant_id"], roles=tuple(data["roles"]))


def get_ticket_store(conn: HTTPConnection) -> TicketStore:
    """The store the lifespan created. HTTPConnection: usable from HTTP and WebSocket routes."""
    return conn.app.state.tickets


router = APIRouter(tags=["websocket"])


@router.post("/ws-tickets", status_code=201)
async def issue_ticket(
    response: Response,
    user: CurrentUser = Depends(get_current_user),  # the same bearer auth as every API route
    tickets: TicketStore = Depends(get_ticket_store),
) -> dict[str, Any]:
    ticket = await tickets.issue(
        TicketClaims(user_id=str(user.user_id), tenant_id=str(user.tenant_id), roles=tuple(user.roles))
    )
    response.headers["Cache-Control"] = "no-store"
    return {"data": {"ticket": ticket, "expires_in": TICKET_TTL_SECONDS}, "meta": {"request_id": get_request_id()}}
```

## FastAPI WebSocket Endpoint

```python
# app/ws/endpoint.py

import json
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
import structlog

from app.ws.handlers import handle_message, send_error
from app.ws.manager import Connection, manager
from app.ws.tickets import TicketStore, get_ticket_store

logger = structlog.get_logger(__name__)
router = APIRouter()

MAX_MESSAGE_SIZE = 65536  # 64KB


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: str = Query("", description="single-use ticket from POST /api/v1/ws-tickets"),
    tickets: TicketStore = Depends(get_ticket_store),
) -> None:
    """WebSocket endpoint authenticated by a single-use ticket — never a bearer token in the URL."""

    # 1. Accept, then authenticate. A close BEFORE accept is a refused handshake (ASGI: HTTP 403), which
    #    browsers report only as 1006. After accept the client gets close code 4001 and a reason, and
    #    nothing is read from the socket before the ticket is redeemed.
    await websocket.accept()
    claims = await tickets.redeem(ticket) if ticket else None
    if claims is None:
        logger.warning("ws.auth_failed")  # never log the ticket
        await websocket.close(code=4001, reason="unauthorized")
        return

    # 2. Create and register connection
    conn = Connection(
        id=str(uuid.uuid4()),
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        roles=list(claims.roles),
        websocket=websocket,
    )
    await manager.register(conn)

    try:
        # 3. Message loop
        while True:
            raw = await websocket.receive_text()

            # Size check
            if len(raw) > MAX_MESSAGE_SIZE:
                await send_error(conn, None, "MESSAGE_TOO_LARGE", "Message exceeds size limit")
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_error(conn, None, "INVALID_JSON", "Malformed JSON")
                continue

            await handle_message(conn, msg)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("ws.error", conn_id=conn.id, error=str(exc))
    finally:
        await manager.unregister(conn)
```

## Message Handler

```python
# app/ws/handlers.py

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.ws.manager import Connection, manager

logger = structlog.get_logger(__name__)


async def handle_message(conn: Connection, msg: dict[str, Any]) -> None:
    """Dispatch incoming WebSocket messages by type."""
    msg_type = msg.get("type")
    ref = msg.get("id")  # client message ID for acknowledgement

    match msg_type:
        case "subscribe":
            room = msg.get("payload", {}).get("room")
            if not room:
                await send_error(conn, ref, "INVALID_PAYLOAD", "room is required")
                return

            if not can_join_room(conn, room):
                await send_error(conn, ref, "FORBIDDEN", "not authorized for this room")
                return

            await manager.subscribe(conn, room)
            await send_ack(conn, ref)

        case "unsubscribe":
            room = msg.get("payload", {}).get("room")
            if room:
                await manager.unsubscribe(conn, room)
            await send_ack(conn, ref)

        case "message":
            payload = msg.get("payload", {})
            room = payload.get("room")
            data = payload.get("data")

            if not room or room not in conn.rooms:
                await send_error(conn, ref, "NOT_IN_ROOM", "not subscribed to this room")
                return

            await manager.broadcast_to_room(
                room,
                {
                    "type": "message",
                    "payload": data,
                    "room": room,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                except_conn_id=conn.id,
            )
            await send_ack(conn, ref)

        case _:
            await send_error(conn, ref, "UNKNOWN_TYPE", f"unknown message type: {msg_type}")


def can_join_room(conn: Connection, room: str) -> bool:
    """
    Deny by default. A room is "tenant:<tenant_id>" or "tenant:<tenant_id>:<topic>", and only
    connections of that tenant may join it (the tenant comes from the redeemed ticket, never from the
    client). Add finer rules here (project membership, roles) as new room kinds appear.
    """
    kind, _, rest = room.partition(":")
    return kind == "tenant" and rest.split(":", 1)[0] == conn.tenant_id


async def send_ack(conn: Connection, ref: str | None) -> None:
    if ref:
        await conn.websocket.send_json({"type": "ack", "ref": ref})


async def send_error(conn: Connection, ref: str | None, code: str, message: str) -> None:
    msg = {"type": "error", "code": code, "message": message}
    if ref:
        msg["ref"] = ref
    await conn.websocket.send_json(msg)
```

## Django Channels Alternative

```python
# myapp/consumers.py

import logging
import re
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from myapp.tickets import redeem_ticket  # atomic GET+DELETE of a single-use ticket (as app/ws/tickets.py)

logger = logging.getLogger(__name__)


def group_name(room: str) -> str:
    """Channels group names allow only ASCII letters, digits, "-", "_" and "." (max 100)."""
    return re.sub(r"[^A-Za-z0-9._-]", ".", room)[:100]


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Django Channels WebSocket consumer for real-time notifications."""

    async def connect(self):
        # A single-use ticket from an authenticated POST — never a bearer token in the URL. Accept
        # first: a close before accept reaches the client as a refused handshake, not code 4001.
        ticket = parse_qs(self.scope["query_string"].decode()).get("ticket", [""])[0]
        claims = await redeem_ticket(ticket) if ticket else None
        await self.accept()
        if claims is None:
            await self.close(code=4001)
            return

        self.claims = claims
        self.room_group = group_name(f"user_{claims.user_id}")

        # Join user-specific group
        await self.channel_layer.group_add(self.room_group, self.channel_name)

        logger.info("ws.connected", extra={"user_id": claims.user_id})

    async def disconnect(self, code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        logger.info("ws.disconnected", extra={"code": code})

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        if msg_type == "subscribe":
            room = content.get("payload", {}).get("room")
            if room and self.can_join(room):
                await self.channel_layer.group_add(group_name(room), self.channel_name)
                await self.send_json({"type": "ack", "ref": content.get("id")})
            else:
                await self.send_json({"type": "error", "code": "FORBIDDEN",
                                      "message": "not authorized for this room", "ref": content.get("id")})

    # Handler for messages sent via channel_layer.group_send
    async def notification(self, event):
        await self.send_json({
            "type": "notification",
            "payload": event["payload"],
            "timestamp": event["timestamp"],
        })

    def can_join(self, room: str) -> bool:
        """The same rule as can_join_room in app/ws/handlers.py: only the caller's tenant's rooms."""
        kind, _, rest = room.partition(":")
        return kind == "tenant" and rest.split(":", 1)[0] == self.claims.tenant_id
```

```python
# myapp/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
]
```

## Heartbeat with Background Task

```python
# app/ws/heartbeat.py

import asyncio

from app.ws.manager import manager


async def heartbeat_loop(interval: float = 30.0) -> None:
    """Send periodic pings to detect dead connections.
    FastAPI/Starlette handles protocol-level pings, but this
    can be used for application-level heartbeat if needed.
    """
    while True:
        await asyncio.sleep(interval)
        # Starlette/uvicorn handles WebSocket ping/pong at protocol level
        # This loop can be used to check for stale connections
        # and force-disconnect them if needed.
```

## Application Wiring

```python
# app/main.py

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import settings
from app.dependencies.auth import JWTConfig, configure_jwt
from app.errors.handlers import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware
from app.ws.endpoint import router as ws_router
from app.ws.tickets import RedisTicketStore
from app.ws.tickets import router as tickets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: the ticket store, in the Redis every replica shares (REDIS_URL from the environment)
    redis = Redis.from_url(os.environ["REDIS_URL"])
    app.state.tickets = RedisTicketStore(redis)
    yield
    # Shutdown: manager cleanup happens via WebSocketDisconnect handlers
    await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="WebSocket API", lifespan=lifespan)
    # The ticket endpoint authenticates like every API route (auth-middleware-python.md)
    configure_jwt(JWTConfig(
        secret_key=settings.jwt_secret_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    ))
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)
    app.include_router(tickets_router, prefix="/api/v1")  # POST /api/v1/ws-tickets
    app.include_router(ws_router)                         # GET /ws?ticket=...
    return app
```

## Critical Rules

- Authenticate the upgrade with a single-use ticket (`POST /api/v1/ws-tickets`, redeemed with an atomic GET+DELETE) — never a bearer token in the URL
- On an auth failure, `accept()` then `close(code=4001)`: a close before accept is a refused handshake (HTTP 403 under ASGI), which browsers report only as 1006
- Use `asyncio.Lock` for connection manager state — Python asyncio is single-threaded but needs lock for coroutine safety
- Always wrap `send_json` in try/except — client may disconnect between check and send
- Clean up in `finally` block — `unregister` MUST run even on unexpected errors
- Room authorization in `can_join_room` MUST check tenant isolation and deny by default: a room is `tenant:<tenant_id>[:topic]`, joinable only by that tenant's connections
- Channels group names allow only `[A-Za-z0-9._-]` (max 100): map room names with `group_name()`
- For Django Channels: use `channel_layer.group_send` for cross-process broadcasting
- FastAPI WebSocket does not support HTTP middleware — auth must happen in the endpoint
- Set `MAX_MESSAGE_SIZE` and check `len(raw)` before parsing — prevent memory exhaustion
