"""harness: run testing/load-testing.md's locustfile headless (real locust, its own process) against a
local stand-in for the widget API that answers in the envelope and, like the real one, rejects what the
envelope doesn't define (an unknown query parameter, a limit outside 1..100, a missing bearer token).
Fails when any locust request failed or when a task never ran."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

TOKEN = "harness-token"


class WidgetAPI(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # quiet
        pass

    def _send(self, status: int, body: dict[str, object]) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, status: int, code: str, field: str = "") -> None:
        err: dict[str, object] = {"code": code, "message": code, "request_id": "r", "retryable": False}
        if field:
            err["details"] = [{"field": field, "code": "invalid", "message": "invalid"}]
        self._send(status, {"error": err})

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._error(401, "UNAUTHENTICATED")
            return False
        return True

    def do_POST(self) -> None:
        if not self._authorized():
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        self._send(201, {"data": {"id": str(uuid.uuid4()), "name": body["name"]}, "meta": {"request_id": "r"}})

    def do_GET(self) -> None:
        if not self._authorized():
            return
        url = urlsplit(self.path)
        if url.path == "/api/v1/widgets":
            params = parse_qs(url.query)
            unknown = set(params) - {"cursor", "limit"}
            if unknown:
                self._error(400, "VALIDATION_FAILED", sorted(unknown)[0])
                return
            limit = int(params.get("limit", ["20"])[0])
            if not 1 <= limit <= 100:
                self._error(400, "VALIDATION_FAILED", "limit")
                return
            pagination = {"next_cursor": None, "has_more": False, "limit": limit}
            self._send(200, {"data": [], "meta": {"request_id": "r", "pagination": pagination}})
        elif url.path.startswith("/api/v1/widgets/"):
            self._send(200, {"data": {"id": url.path.rsplit("/", 1)[1], "name": "w"}, "meta": {"request_id": "r"}})
        else:
            self._error(404, "NOT_FOUND")


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), WidgetAPI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {**os.environ, "APP_BASE_URL": f"http://127.0.0.1:{server.server_port}", "AUTH_TOKEN": TOKEN}
    cmd = [sys.executable, "-m", "locust", "-f", "locustfile.py", "--headless", "--users", "4",
           "--spawn-rate", "4", "--run-time", "5s", "--only-summary", "--csv", "harness_locust",
           "--exit-code-on-error", "1"]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    server.shutdown()
    with open("harness_locust_stats.csv", newline="") as f:
        rows = {(r["Type"], r["Name"]): r for r in csv.DictReader(f)}
    failures = int(rows[("", "Aggregated")]["Failure Count"])
    list_requests = int(rows.get(("GET", "/api/v1/widgets?limit=20"), {}).get("Request Count", 0))
    creates = int(rows.get(("POST", "/api/v1/widgets"), {}).get("Request Count", 0))
    reads = sum(int(r["Request Count"]) for (t, n), r in rows.items() if t == "GET" and n.startswith("/api/v1/widgets/"))
    print(f"locust exit {p.returncode}: failures={failures} list={list_requests} create={creates} get={reads}")
    if p.returncode != 0 or failures or not (list_requests and creates and reads):
        print(p.stdout[-3000:], p.stderr[-3000:])
        with open("harness_locust_failures.csv", newline="") as f:
            print(f.read()[-2000:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
