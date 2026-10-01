# languages/python.md, the general blocks: each runs. HTTP goes to a local server that records how many
# requests are in flight at once (the semaphore's limit) and holds each one briefly.
import asyncio
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docs_fragments import domain_errors, perf, semaphores, shutdown, task_groups, types
from harness_stubs.py_basics import DBConnectionError, RepositoryError, User, UserNotFoundError, db

# Error Handling: the infrastructure error is wrapped, with the cause chained
db.down = True
try:
    asyncio.run(domain_errors.get_user("u1"))
except RepositoryError as exc:
    assert isinstance(exc.__cause__, DBConnectionError), exc.__cause__
else:
    raise AssertionError("expected RepositoryError")
db.down = False

# Type Safety: overloads, Literal, generic TypedDicts
u = User()
db.users["u1"] = u
assert types.fetch("u1", required=True) is u and types.fetch("nope") is None
try:
    types.fetch("nope", required=True)
except UserNotFoundError:
    pass
else:
    raise AssertionError("expected UserNotFoundError")
assert types.first_or_none([3, 4]) == 3 and types.first_or_none([]) is None
page: types.PaginatedResponse[int] = {"data": [], "meta": {"request_id": "r", "pagination": {
    "next_cursor": None, "has_more": False, "limit": 20}}}
assert page["data"] == []


class Slow(BaseHTTPRequestHandler):
    in_flight = 0
    peak = 0
    lock = threading.Lock()

    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        with Slow.lock:
            Slow.in_flight += 1
            Slow.peak = max(Slow.peak, Slow.in_flight)
        time.sleep(0.05)
        with Slow.lock:
            Slow.in_flight -= 1
        body = self.path.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
try:
    urls = [f"{base}/item/{i}" for i in range(12)]
    responses = asyncio.run(semaphores.fetch_many(urls, max_concurrent=3))
    assert [r.text for r in responses] == [f"/item/{i}" for i in range(12)]  # bodies readable after return
    assert 1 <= Slow.peak <= 3, Slow.peak
    Slow.peak = 0
    responses = asyncio.run(perf.fetch_all(urls[:4]))
    assert [r.status_code for r in responses] == [200] * 4 and responses[0].text == "/item/0"
finally:
    server.shutdown()

# Performance helpers
with tempfile.TemporaryDirectory() as tmp:
    log_file = Path(tmp) / "app.log"
    log_file.write_text("ok\nERROR a\nERROR b\nfine\n")
    assert perf.process_large_file(log_file) == 2
assert perf.fibonacci(30) == 832040
assert not hasattr(perf.Point(1, 2, 3), "__dict__")  # slots
assert perf.Config('[db]\npool = 5\n').parsed == {"db": {"pool": 5}}
results = perf.process_images([Path("a.png"), Path("bb.png")])  # a real process pool
assert [r.size for r in results] == [5, 6], results

# TaskGroup: all results, or the first failure with the siblings cancelled
profile = asyncio.run(task_groups.fetch_user_data("u1"))
assert profile.orders == ["o1", "o2"] and profile.preferences == {"dark": True}
try:
    asyncio.run(task_groups.fetch_user_data("broken"))
except* RuntimeError:
    pass

# Graceful shutdown: the lifespan opens the resources and closes them on shutdown
app = FastAPI(lifespan=shutdown.lifespan)
with TestClient(app):
    pool = app.state.db_pool
    assert not pool.closed
assert pool.closed
