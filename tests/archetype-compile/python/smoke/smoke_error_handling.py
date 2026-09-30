# harness smoke: register_exception_handlers writes the one error envelope (api/response-envelope.md)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import NotFoundError, RateLimitError, UnavailableError
from app.errors.handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)


@app.get("/nf")
async def nf() -> None:
    raise NotFoundError("Widget")


@app.get("/rl")
async def rl() -> None:
    raise RateLimitError(3)


@app.get("/down")
async def down() -> None:
    raise UnavailableError("postgres", cause=TimeoutError("statement timeout"))


@app.get("/boom")
async def boom() -> None:
    raise RuntimeError("secret internals")


@app.get("/q")
async def q(limit: int) -> dict[str, int]:
    return {"limit": limit}


c = TestClient(app, raise_server_exceptions=False)
r = c.get("/nf")
body = r.json()
assert r.status_code == 404, r.text
assert body == {"error": {"code": "NOT_FOUND", "message": "Widget not found.",
                          "request_id": r.headers["x-request-id"], "retryable": False}}, body
r = c.get("/rl")
assert r.status_code == 429 and r.headers["retry-after"] == "3" and r.json()["error"]["retryable"] is True, r.text
r = c.get("/down")
assert r.status_code == 503 and "postgres" not in r.text and "timeout" not in r.text, r.text
r = c.get("/boom")
assert r.status_code == 500 and "secret" not in r.text and r.json()["error"]["code"] == "INTERNAL", r.text
r = c.get("/q?limit=x")
assert r.status_code == 400, r.text
assert r.json()["error"]["details"] == [{"field": "limit", "code": "int_parsing", "message": "Must be a whole number."}], r.text
r = c.get("/missing")
assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND", r.text
r = c.post("/nf")
assert r.status_code == 400 and r.json()["error"]["code"] == "MALFORMED_REQUEST", r.text  # 405 → re-shaped by status
