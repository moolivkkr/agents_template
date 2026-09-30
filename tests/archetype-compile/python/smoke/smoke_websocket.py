# harness smoke: run websocket-pattern-python.md's FastAPI app with two real WebSocket clients.
# `with TestClient(...)` runs every session on ONE event loop, as a real server does. Outside the
# `with`, each session gets its own loop, and a manager shared between connections would span two.
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app

with TestClient(create_app()) as c:
    try:
        with c.websocket_connect("/ws?token=forged") as ws:
            ws.receive_text()
        raise AssertionError("a bad token was accepted")
    except WebSocketDisconnect:
        pass  # closed before accept

    with c.websocket_connect("/ws?token=valid:t1:u1") as a, c.websocket_connect("/ws?token=valid:t1:u2") as b:
        a.send_json({"type": "subscribe", "id": "1", "payload": {"room": "tenant:t1"}})
        assert a.receive_json() == {"type": "ack", "ref": "1"}
        b.send_json({"type": "subscribe", "id": "2", "payload": {"room": "tenant:t1"}})
        assert b.receive_json() == {"type": "ack", "ref": "2"}

        a.send_json({"type": "message", "id": "3", "payload": {"room": "tenant:t1", "data": {"hello": 1}}})
        got = b.receive_json()
        assert got["type"] == "message" and got["payload"] == {"hello": 1} and got["room"] == "tenant:t1", got
        assert a.receive_json() == {"type": "ack", "ref": "3"}

        a.send_json({"type": "message", "id": "4", "payload": {"room": "elsewhere", "data": 1}})
        assert a.receive_json()["code"] == "NOT_IN_ROOM"
        a.send_text("{not json")
        assert a.receive_json()["code"] == "INVALID_JSON"
        a.send_text("x" * 70_000)
        assert a.receive_json()["code"] == "MESSAGE_TOO_LARGE"
        a.send_json({"type": "nope", "id": "5"})
        assert a.receive_json() == {"type": "error", "code": "UNKNOWN_TYPE", "message": "unknown message type: nope",
                                    "ref": "5"}

# the Django Channels consumer and routing import under a minimal Django setup
import django  # noqa: E402

django.setup()
from myapp.routing import websocket_urlpatterns  # noqa: E402

assert len(websocket_urlpatterns) == 1
