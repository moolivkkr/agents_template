"""Prove run.sh fails on bad samples: copy the archetypes, break one thing, run the affected unit, and
expect a non-zero exit that names the problem. Run after changing the harness:

    .venv/bin/python selftest.py      (after ./run.sh has created .venv)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / ".claude" / "skills" / "backend" / "archetypes"

# (what, markdown file, text to replace, replacement, unit, text the failure output must contain)
MUTATIONS = [
    ("import of a name app.errors doesn't define", "auth-middleware-python.md",
     "from app.errors import ForbiddenError, UnauthenticatedError",
     "from app.errors import ForbiddenError, UnauthorizedError", "auth-middleware", '"UnauthorizedError" is unknown'),
    ("misspelled SQLAlchemy method", "crud-repository-python.md",
     "stmt = stmt.limit(filters.page_size + 1)", "stmt = stmt.limt(filters.page_size + 1)",
     "crud-repository", "limt"),
    ("raw path as a metric label", "observability-python.md",
     'attrs["http.route"] = route.path', 'attrs["http.route"] = request.url.path',
     "observability", "/api/v1/orders/123"),
    ("upper bound on limit removed", "crud-handler-python.md",
     'limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),',
     'limit: int = Query(20, ge=1, description="Items per page (max 100)"),',
     "crud-handler-test", "exceeds-max"),
    ("new block the config doesn't know", "worker-pattern-python.md",
     "## Critical Rules", "```python\nprint('new')\n```\n\n## Critical Rules", "worker", "EXPECTED says 8"),
    ("WebSocket Origin check removed", "websocket-pattern-python.md",
     "    return origin is None or origin in settings.allowed_origins", "    return True",
     "websocket", "a foreign origin's handshake was accepted"),
    ("SQL span hook not attached", "observability-python.md",
     '    event.listen(target, "before_cursor_execute", _start_span)', "    pass",
     "observability", "expected 2 SQL spans"),
]


def main() -> int:
    ok = True
    for what, md, old, new, unit, expect in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "archetypes"
            shutil.copytree(SRC, dst)
            text = (dst / md).read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"STALE   {what}: the text to break isn't in {md} exactly once; update selftest.py")
                ok = False
                continue
            (dst / md).write_text(text.replace(old, new), encoding="utf-8")
            p = subprocess.run([str(HERE / "run.sh"), "--unit", unit], env={**os.environ, "ARCHETYPE_DIR": str(dst)},
                               capture_output=True, text=True, timeout=1800)
        out = p.stdout + p.stderr
        caught = p.returncode != 0 and expect in out
        ok = ok and caught
        print(f"{'CAUGHT' if caught else 'MISSED'}  {what} (unit {unit}, exit {p.returncode})")
        if not caught:
            print(out[-2000:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
