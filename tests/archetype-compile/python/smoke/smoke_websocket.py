# harness smoke: websocket-pattern-python.md end to end — a ticket from the authenticated POST, the
# /ws upgrade through TestClient AND a real uvicorn server with a real `websockets` client, the Origin
# allowlist, tenant-scoped rooms, and the Channels application (BrowserOriginValidator + consumer) under
# WebsocketCommunicator. The ticket stores are in-memory stand-ins here (--live runs RedisTicketStore and
# myapp/tickets.py on a real Redis).
import asyncio
import secrets
import socket
import time
import uuid

import jwt
import uvicorn
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from app.config import settings
from app.main import create_app
from app.ws.tickets import TicketClaims, get_ticket_store


class MemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, TicketClaims] = {}

    async def issue(self, claims: TicketClaims) -> str:
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = claims
        return ticket

    async def redeem(self, ticket: str) -> TicketClaims | None:
        return self._tickets.pop(ticket, None)


store = MemoryTicketStore()
app = create_app()
app.dependency_overrides[get_ticket_store] = lambda: store

T1, T2 = uuid.uuid4(), uuid.uuid4()


def bearer(tenant: uuid.UUID) -> dict[str, str]:
    claims = {"sub": str(uuid.uuid4()), "tenant_id": str(tenant), "iss": settings.jwt_issuer,
              "aud": settings.jwt_audience, "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(claims, settings.jwt_secret_key, algorithm='HS256')}"}


with TestClient(app) as c:
    # tickets come only from an authenticated POST, in the envelope
    assert c.post("/api/v1/ws-tickets").status_code == 401
    r = c.post("/api/v1/ws-tickets", headers=bearer(T1))
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store", r.text
    body = r.json()
    assert set(body) == {"data", "meta"} and body["meta"]["request_id"] == r.headers["x-request-id"], body

    def ticket(tenant: uuid.UUID) -> str:
        return c.post("/api/v1/ws-tickets", headers=bearer(tenant)).json()["data"]["ticket"]

    # Origin: a foreign page's handshake is refused outright (close before accept), and its ticket isn't
    # even looked up: the same ticket still works from an allowed origin, or with no Origin (not a browser)
    held = ticket(T1)
    try:
        with c.websocket_connect(f"/ws?ticket={held}", headers={"origin": "https://evil.example"}):
            raise AssertionError("a foreign origin's handshake was accepted")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008, exc.code
    with c.websocket_connect(f"/ws?ticket={held}", headers={"origin": "http://localhost:3000"}) as ws:
        ws.send_json({"type": "subscribe", "id": "o", "payload": {"room": f"tenant:{T1}"}})
        assert ws.receive_json() == {"type": "ack", "ref": "o"}

    # no ticket / a made-up ticket: accepted, then closed with 4001
    for url in ("/ws", "/ws?ticket=forged"):
        with c.websocket_connect(url) as ws:
            try:
                ws.receive_text()
                raise AssertionError(f"{url}: expected a close")
            except WebSocketDisconnect as exc:
                assert exc.code == 4001, (url, exc.code)

    t_a = ticket(T1)
    with c.websocket_connect(f"/ws?ticket={t_a}") as a, \
            c.websocket_connect(f"/ws?ticket={ticket(T1)}") as b, \
            c.websocket_connect(f"/ws?ticket={ticket(T2)}") as other:
        room = f"tenant:{T1}"
        a.send_json({"type": "subscribe", "id": "1", "payload": {"room": room}})
        assert a.receive_json() == {"type": "ack", "ref": "1"}
        b.send_json({"type": "subscribe", "id": "2", "payload": {"room": f"{room}:orders"}})
        assert b.receive_json() == {"type": "ack", "ref": "2"}
        # another tenant can't join tenant 1's rooms; unknown room kinds are denied by default
        for rid, bad_room in (("3", room), ("4", f"{room}:orders"), ("5", "project:1"), ("6", "tenant:")):
            other.send_json({"type": "subscribe", "id": rid, "payload": {"room": bad_room}})
            reply = other.receive_json()
            assert reply["code"] == "FORBIDDEN" and reply["ref"] == rid, (bad_room, reply)
        b.send_json({"type": "subscribe", "id": "7", "payload": {"room": room}})
        assert b.receive_json() == {"type": "ack", "ref": "7"}

        a.send_json({"type": "message", "id": "8", "payload": {"room": room, "data": {"hello": 1}}})
        got = b.receive_json()
        assert got["type"] == "message" and got["payload"] == {"hello": 1} and got["room"] == room, got
        assert a.receive_json() == {"type": "ack", "ref": "8"}

        a.send_text("{not json")
        assert a.receive_json()["code"] == "INVALID_JSON"
        a.send_text("x" * 70_000)
        assert a.receive_json()["code"] == "MESSAGE_TOO_LARGE"

    # the same ticket twice: single use
    with c.websocket_connect(f"/ws?ticket={t_a}") as ws:
        try:
            ws.receive_text()
            raise AssertionError("a used ticket was accepted")
        except WebSocketDisconnect as exc:
            assert exc.code == 4001


# the same behaviour on a real server: the client sees close code 4001 (not a refused handshake)
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def real_server() -> None:
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="auto"))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    try:
        try:
            async with connect(f"ws://127.0.0.1:{port}/ws?ticket=forged") as ws:
                await ws.recv()
            raise AssertionError("a forged ticket was accepted")
        except ConnectionClosed as exc:
            assert exc.rcvd is not None and exc.rcvd.code == 4001 and exc.rcvd.reason == "unauthorized", exc
        # a foreign Origin: the server refuses the handshake with HTTP 403
        try:
            async with connect(f"ws://127.0.0.1:{port}/ws?ticket=forged", origin=Origin("https://evil.example")):
                pass
            raise AssertionError("a foreign origin's handshake was accepted")
        except InvalidStatus as exc:
            assert exc.response.status_code == 403, exc
        good = await store.issue(TicketClaims(user_id="u1", tenant_id=str(T1), roles=()))
        async with connect(f"ws://127.0.0.1:{port}/ws?ticket={good}") as ws:
            await ws.send('{"type": "subscribe", "id": "1", "payload": {"room": "tenant:%s"}}' % T1)
            assert await ws.recv() == '{"type":"ack","ref":"1"}'
    finally:
        server.should_exit = True
        await serving


asyncio.run(real_server())


# the Django Channels application (myapp/asgi.py: BrowserOriginValidator around the URL router) and its
# consumer, run by channels' own test communicator. The consumer's redeem_ticket is swapped for an
# in-memory one here; --live runs myapp/tickets.py on Redis through the same application.
import django  # noqa: E402

django.setup()
from channels.testing import WebsocketCommunicator  # noqa: E402

import myapp.consumers as consumers_module  # noqa: E402
from myapp.asgi import application  # noqa: E402
from myapp.routing import websocket_urlpatterns  # noqa: E402
from myapp.tickets import TicketClaims as DjangoClaims  # noqa: E402

_django_tickets: dict[str, DjangoClaims] = {}


async def _memory_redeem(ticket: str) -> DjangoClaims | None:
    return _django_tickets.pop(ticket, None)


consumers_module.redeem_ticket = _memory_redeem  # harness stand-in for the non-live smoke
ALLOWED = [(b"origin", b"http://localhost:3000")]


def communicator(path: str, headers: list[tuple[bytes, bytes]]) -> WebsocketCommunicator:
    return WebsocketCommunicator(application, path, headers=headers)


async def channels_app() -> None:
    held = "held-ticket"
    _django_tickets[held] = DjangoClaims(user_id="u1", tenant_id="t1", roles=())

    # a foreign Origin: refused before the consumer runs (the ticket stays unredeemed)
    foreign = communicator(f"/ws/notifications/?ticket={held}", [(b"origin", b"https://evil.example")])
    connected, _ = await foreign.connect()
    assert not connected
    assert held in _django_tickets

    # allowed Origin, and no Origin (not a browser): on to the ticket check
    for headers in (ALLOWED, []):
        comm = communicator("/ws/notifications/?ticket=forged", headers)
        connected, _ = await comm.connect()
        assert connected  # accepted first ...
        closed = await comm.receive_output()
        assert closed["type"] == "websocket.close" and closed["code"] == 4001, closed  # ... then 4001

    comm = communicator(f"/ws/notifications/?ticket={held}", ALLOWED)
    connected, _ = await comm.connect()
    assert connected
    await comm.send_json_to({"type": "subscribe", "id": "1", "payload": {"room": "tenant:t1:orders"}})
    assert await comm.receive_json_from() == {"type": "ack", "ref": "1"}
    await comm.send_json_to({"type": "subscribe", "id": "2", "payload": {"room": "tenant:t2"}})
    assert (await comm.receive_json_from())["code"] == "FORBIDDEN"
    await comm.disconnect()

    reused = communicator(f"/ws/notifications/?ticket={held}", ALLOWED)
    await reused.connect()
    assert (await reused.receive_output())["code"] == 4001  # single use


asyncio.run(channels_app())
assert len(websocket_urlpatterns) == 1
