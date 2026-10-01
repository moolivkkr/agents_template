"""harness: `alembic upgrade head --sql` stops at the batched backfill with its own message, after
rendering the revisions before it, instead of printing one batch that would look like the whole job."""
import subprocess
import sys

r = subprocess.run(
    [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head", "--sql"],
    capture_output=True, text=True,
)
assert r.returncode != 0, "an offline upgrade through the batched backfill should fail"
assert "the batched category backfill needs a live database" in r.stderr, r.stderr[-2000:]
assert "UPDATE alembic_version SET version_num='d4e5f6a7b8c9'" in r.stdout, r.stdout[-2000:]
print("offline: rendered up to d4e5f6a7b8c9, then refused the batched backfill")
