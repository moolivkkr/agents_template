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

## FastAPI WebSocket Endpoint

```python
# app/ws/endpoint.py

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import structlog

from app.ws.manager import Connection, manager
from app.auth.jwt import validate_jwt, JWTError

logger = structlog.get_logger(__name__)
router = APIRouter()

MAX_MESSAGE_SIZE = 65536  # 64KB

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT bearer token"),
) -> None:
    """WebSocket endpoint with JWT authentication on upgrade."""

    # 1. Authenticate
    try:
        claims = validate_jwt(token)
    except JWTError as exc:
        logger.warning("ws.auth_failed", error=str(exc))
        await websocket.close(code=4001, reason="unauthorized")
        return

    # 2. Accept connection
    await websocket.accept()

    # 3. Create and register connection
    conn = Connection(
        id=str(uuid.uuid4()),
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        roles=claims.roles,
        websocket=websocket,
    )
    await manager.register(conn)

    try:
        # 4. Message loop
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
    """Check if the connection is authorized to join this room."""
    # Implement room-level authorization:
    # e.g., "tenant:{id}" requires matching tenant_id
    # e.g., "project:{id}" requires project membership
    return True  # Replace with actual logic

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

import json
import logging
from channels.generic.websocket import AsyncJsonWebSocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncJsonWebSocketConsumer):
    """Django Channels WebSocket consumer for real-time notifications."""

    async def connect(self):
        # Authentication (token from query string)
        token = self.scope["query_string"].decode().split("token=")[-1]
        try:
            self.user = await self.authenticate(token)
        except Exception:
            await self.close(code=4001)
            return

        self.room_group = f"user_{self.user.id}"

        # Join user-specific group
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        logger.info("ws.connected", extra={"user_id": str(self.user.id)})

    async def disconnect(self, close_code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        logger.info("ws.disconnected", extra={"code": close_code})

    async def receive_json(self, content):
        msg_type = content.get("type")

        if msg_type == "subscribe":
            room = content.get("payload", {}).get("room")
            if room and await self.can_join(room):
                await self.channel_layer.group_add(room, self.channel_name)
                await self.send_json({"type": "ack", "ref": content.get("id")})

    # Handler for messages sent via channel_layer.group_send
    async def notification(self, event):
        await self.send_json({
            "type": "notification",
            "payload": event["payload"],
            "timestamp": event["timestamp"],
        })

    @database_sync_to_async
    def authenticate(self, token):
        # Validate JWT and return user
        pass

    @database_sync_to_async
    def can_join(self, room):
        # Check room authorization
        return True
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

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.ws.endpoint import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: manager cleanup happens via WebSocketDisconnect handlers

def create_app() -> FastAPI:
    app = FastAPI(title="WebSocket API", lifespan=lifespan)
    app.include_router(ws_router)
    return app
```

## Critical Rules

- Use `websocket.close(code=4001)` for auth failures — never silently drop
- Use `asyncio.Lock` for connection manager state — Python asyncio is single-threaded but needs lock for coroutine safety
- Always wrap `send_json` in try/except — client may disconnect between check and send
- Clean up in `finally` block — `unregister` MUST run even on unexpected errors
- Room authorization in `can_join_room` MUST check tenant isolation
- For Django Channels: use `channel_layer.group_send` for cross-process broadcasting
- FastAPI WebSocket does not support HTTP middleware — auth must happen in the endpoint
- Set `MAX_MESSAGE_SIZE` and check `len(raw)` before parsing — prevent memory exhaustion
