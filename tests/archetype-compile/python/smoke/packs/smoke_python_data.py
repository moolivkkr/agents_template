# languages/python.md data blocks without a database: the pooled engine is configured from the
# environment and not connected (--live connects it, runs the repository, the service transaction, the
# Alembic env, the fixtures and the asyncpg context manager against PostgreSQL 16).
from app.engine import engine

assert engine.url.render_as_string(hide_password=False) == "postgresql+asyncpg://harness@127.0.0.1:1/harness"
assert engine.pool.size() == 20
