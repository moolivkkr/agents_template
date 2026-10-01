"""Which markdown blocks make up which checked project ("unit"), and what each unit runs.

Block references are (markdown file, 0-based index among its ```python blocks, anchor). The anchor is
the block's first non-empty line; harness.py refuses to run when it no longer matches, and when a
file's block count differs from EXPECTED. So an edit that adds, removes or reorders a block fails
loudly here until the mapping is looked at again.

Units are assembled from the REAL blocks of the archetype files they depend on (the crud-handler unit
imports the crud-service and error-handling blocks, not stand-ins), so a name one archetype uses and
another doesn't define is caught. stubs/ holds only app-level names that a fragment deliberately leaves
to the reader (an Order model, a settings object); never a library API a sample demonstrates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class B:
    """A ```python block. wrap: header line to nest a fragment in (e.g. a bare top-level `await`)."""

    md: str
    index: int
    anchor: str
    wrap: str | None = None
    # exact whole-line substitutions (old, new); used only to give a fragment's class a harness base
    subs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class T:
    """Harness text (imports a fragment omits, a pyright directive, glue)."""

    text: str


@dataclass(frozen=True)
class S:
    """A file from stubs/ (harness-only app-level stand-ins)."""

    path: str


@dataclass(frozen=True)
class MD:
    """A non-Python fenced block used as an input file, read-only (alembic.ini, .proto files)."""

    md: str
    lang: str
    index: int
    anchor: str


@dataclass
class Unit:
    name: str
    own: list[str]  # markdown files whose blocks this unit reports on
    files: dict[str, list[B | T | S | MD]]
    typecheck: list[str] | None = None  # default: every .py built from an `own` block
    imports: list[str] | None = None  # default: the typecheck files outside tests/ and alembic/
    smoke: str | None = None  # harness Python run after the imports (no external services)
    pytest: str | None = None  # "collect" | "run"
    pytest_args: list[str] = field(default_factory=list)
    live: str | None = None  # pytest mode with --live (Docker Postgres), e.g. "run"
    pre: list[list[str]] = field(default_factory=list)  # commands before the checks; {py} = venv python
    post: list[list[str]] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    pyright: dict[str, object] = field(default_factory=dict)  # pyrightconfig overrides (keep rare, say why)
    # Type-checker false positives, each proven wrong at runtime by this unit's smoke/tests:
    # (markdown file, pyright message prefix (whitespace-normalised), code on that exact markdown line,
    # reason). Both must match; printed as IGNORED on every run.
    pyright_ignore: list[tuple[str, str, str, str]] = field(default_factory=list)


def smoke(name: str) -> str:
    """A smoke script from smoke/ (harness code run after the unit's imports)."""
    return (Path(__file__).parent / "smoke" / name).read_text(encoding="utf-8")


AM = "auth-middleware-python.md"
CH = "crud-handler-python.md"
CHT = "crud-handler-test-python.md"
CR = "crud-repository-python.md"
CRT = "crud-repository-test-python.md"
CS = "crud-service-python.md"
CST = "crud-service-test-python.md"
DF = "dockerfile-python.md"
EH = "error-handling-python.md"
GR = "grpc-pattern-python.md"
MG = "migration-pattern-python.md"
OB = "observability-python.md"
PF = "performance-python.md"
WS = "websocket-pattern-python.md"
WK = "worker-pattern-python.md"

EXPECTED = {
    AM: 11, CH: 7, CHT: 11, CR: 15, CRT: 12, CS: 13, CST: 11, DF: 1,
    EH: 7, GR: 5, MG: 10, OB: 23, PF: 28, WS: 10, WK: 8,
}

# Blocks that hold only comments. The harness verifies that; code added to one fails until it gets a unit.
COMMENT_ONLY = [
    (EH, 4, "# --- WRAPPING RULES ---"),
]

# (md, index, anchor) -> reason. Keep empty unless a block truly can't be checked.
SKIPS: dict[tuple[str, int, str], str] = {}


# ── shared building blocks (the real archetype code, reused across units) ──────────────────────────


def errors_pkg() -> dict[str, list[B | T | S | MD]]:
    return {
        "app/errors/base.py": [B(EH, 0, "# app/errors/base.py")],
        "app/errors/domain.py": [B(EH, 1, "# app/errors/domain.py")],
        "app/errors/__init__.py": [B(EH, 2, "# app/errors/__init__.py")],
        "app/errors/handlers.py": [B(EH, 3, "# app/errors/handlers.py")],
    }


def domain_pkg() -> dict[str, list[B | T | S | MD]]:
    return {
        "app/domain/base.py": [B(CS, 0, "# app/domain/base.py")],
        "app/domain/widget.py": [B(CS, 1, "# app/domain/widget.py")],
        "app/services/protocols.py": [B(CS, 2, "# app/services/protocols.py")],
    }


def service_pkg() -> dict[str, list[B | T | S | MD]]:
    return {
        "app/services/widget.py": [
            B(CS, 3, "# app/services/widget.py"),
            B(CS, 4, "async def create("),
            B(CS, 5, "async def get(self, *, tenant_id: UUID, widget_id: UUID) -> Widget:"),
            B(CS, 6, "async def update("),
            B(CS, 7, "async def delete(self, *, tenant_id: UUID, widget_id: UUID) -> None:"),
            B(CS, 8, "async def list("),
            B(CS, 9, "async def create_with_components("),
            B(CS, 10, "@staticmethod"),
            B(CS, 11, "async def _cache_set(self, key: str, widget: Widget) -> None:"),
            B(CS, 12, "async def _audit_log("),
        ],
    }


def handler_request_id() -> dict[str, list[B | T | S | MD]]:
    return {"app/middleware/request_id.py": [B(CH, 3, "# app/middleware/request_id.py")]}


def handler_pkg() -> dict[str, list[B | T | S | MD]]:
    return {
        "app/schemas/base.py": [B(CH, 0, "# app/schemas/base.py")],
        "app/schemas/widget.py": [B(CH, 1, "# app/schemas/widget.py")],
        "app/dependencies/auth.py": [B(CH, 2, "# app/dependencies/auth.py")],
        **handler_request_id(),
        "app/api/v1/widgets.py": [
            B(CH, 4, "# app/api/v1/widgets.py"),
            B(CH, 5, "# Allowed sort and filter fields — prevents SQL injection by allow-listing"),
        ],
        "app/main.py": [B(CH, 6, "# app/main.py")],
    }


def auth_pkg() -> dict[str, list[B | T | S | MD]]:
    """auth-middleware-python.md's settings, JWT dependency and request-id middleware."""
    return {
        "app/config.py": [B(AM, 0, "# app/config.py")],
        "app/dependencies/auth.py": [
            B(AM, 1, "# app/dependencies/auth.py"),
            B(AM, 2, "# app/dependencies/auth.py (continued)"),
        ],
        "app/middleware/request_id.py": [B(AM, 7, "# app/middleware/request_id.py")],
    }


def migration_files() -> dict[str, list[B | T | S | MD]]:
    """migration-pattern-python.md's alembic.ini, env.py and revision chain."""
    return {
        "alembic.ini": [MD(MG, "ini", 0, "# alembic.ini")],
        "alembic/env.py": [B(MG, 0, "# alembic/env.py")],
        "alembic/versions/20260115_095000_create_tenants_table.py": [
            B(MG, 1, "# alembic/versions/20260115_095000_create_tenants_table.py")],
        "alembic/versions/20260115_100000_create_widgets_table.py": [
            B(MG, 2, "# alembic/versions/20260115_100000_create_widgets_table.py")],
        "alembic/versions/20260115_100100_add_widget_categories.py": [
            B(MG, 3, "# alembic/versions/20260115_100100_add_widget_categories.py")],
        "alembic/versions/20260115_100200_seed_default_categories.py": [
            B(MG, 4, "# alembic/versions/20260115_100200_seed_default_categories.py")],
        "alembic/versions/20260115_100300_backfill_widget_category.py": [
            B(MG, 5, "# alembic/versions/20260115_100300_backfill_widget_category.py")],
    }


def repository_pkg() -> dict[str, list[B | T | S | MD]]:
    return {
        "app/models/widget.py": [B(CR, 0, "# app/models/widget.py")],
        "app/db/engine.py": [B(CR, 1, "# app/db/engine.py")],
        "app/db/transaction.py": [B(CR, 2, "# app/db/transaction.py")],
        "app/repositories/widget.py": [
            B(CR, 3, "# app/repositories/widget.py"),
            B(CR, 4, "async def create(self, widget: Widget) -> None:"),
            B(CR, 5, "async def get_by_id(self, tenant_id: UUID, widget_id: UUID) -> Widget | None:"),
            B(CR, 6, "async def update(self, widget: Widget) -> bool:"),
            B(CR, 7, "async def soft_delete(self, tenant_id: UUID, widget_id: UUID) -> bool:"),
            B(CR, 8, "async def list(self, tenant_id: UUID, filters: ListFilters) -> ListResult[Widget]:"),
            B(CR, 9, "# Sequence, not list[...]: in this class body `list` is the method above, so `list[Widget]`"),
            B(CR, 10, "@staticmethod"),
            B(CR, 11, "@staticmethod"),
            B(CR, 12, "_CACHE_TTL = 300  # 5 minutes"),
            B(CR, 13, "@staticmethod"),
        ],
        "app/repositories/widget_raw.py": [B(CR, 14, "# app/repositories/widget_raw.py")],
    }


def service_unit_files() -> dict[str, list[B | T | S | MD]]:
    return {**errors_pkg(), **domain_pkg(), **service_pkg(), **handler_request_id()}


def handler_unit_files() -> dict[str, list[B | T | S | MD]]:
    return {**errors_pkg(), **domain_pkg(), **service_pkg(), **handler_pkg()}


UNITS: list[Unit] = []

# ── error-handling ─────────────────────────────────────────────────────────────────────────────────
UNITS.append(Unit(
    name="error-handling",
    own=[EH],
    files={
        **errors_pkg(),
        **domain_pkg(),
        # "Usage in Service Layer": a sketch of app/services/widget.py
        "app/services/widget.py": [B(EH, 5, "# app/services/widget.py")],
        # "Type Checking Errors": a bare try/except with `await` — only valid inside a coroutine
        "docs_fragments/error_checks.py": [
            S("error_checks_prelude.py"),
            B(EH, 6, "# Use isinstance for error type checking — mirrors Go's errors.As and TypeScript's instanceof",
              wrap="async def _fragment() -> None:"),
        ],
    },
    smoke=smoke("smoke_error_handling.py"),
))

# ── crud-service ───────────────────────────────────────────────────────────────────────────────────
UNITS.append(Unit(
    name="crud-service",
    own=[CS],
    files=service_unit_files(),
))

UNITS.append(Unit(
    name="crud-service-test",
    own=[CST],
    files={
        **service_unit_files(),
        "tests/factories.py": [B(CST, 0, "# tests/factories.py")],
        "tests/services/test_widget_service.py": [
            B(CST, 1, "# tests/services/test_widget_service.py"),
            B(CST, 2, "class TestCreate:"),
            B(CST, 3, "class TestCreateTableDriven:"),
            B(CST, 4, "class TestGet:"),
            B(CST, 5, "class TestUpdate:"),
            B(CST, 6, "class TestDelete:"),
            B(CST, 7, "class TestList:"),
            B(CST, 8, "class TestAuditLogging:"),
            B(CST, 9, "class TestEdgeCases:"),
            B(CST, 10, "class TestTransactionRollback:"),
        ],
    },
    pytest="run",
))

# ── crud-handler ───────────────────────────────────────────────────────────────────────────────────
UNITS.append(Unit(
    name="crud-handler",
    own=[CH],
    files=handler_unit_files(),
    smoke="from app.main import create_app\ncreate_app()\n",
))

UNITS.append(Unit(
    name="crud-handler-test",
    own=[CHT],
    files={
        **handler_unit_files(),
        "tests/conftest.py": [B(CHT, 0, "# tests/conftest.py")],
        "tests/factories.py": [B(CHT, 1, "# tests/factories.py")],
        "tests/api/v1/test_widgets.py": [
            B(CHT, 2, "# tests/api/v1/test_widgets.py"),
            B(CHT, 3, "class TestGetWidget:"),
            B(CHT, 4, "class TestUpdateWidget:"),
            B(CHT, 5, "class TestDeleteWidget:"),
            B(CHT, 6, "class TestListWidgets:"),
            B(CHT, 7, "class TestErrorMapping:"),
            B(CHT, 8, "class TestAuth:"),
            B(CHT, 9, "class TestResponseShape:"),
            B(CHT, 10, "class TestContentType:"),
        ],
    },
    pytest="run",
))

# ── auth-middleware (composed with the real widgets router, service and error handlers) ────────────
def auth_app_files() -> dict[str, list[B | T | S | MD]]:
    """auth-middleware-python.md's create_app() with the real widgets router, service and errors."""
    return {
        **errors_pkg(),
        **domain_pkg(),
        **service_pkg(),
        "app/schemas/base.py": [B(CH, 0, "# app/schemas/base.py")],
        "app/schemas/widget.py": [B(CH, 1, "# app/schemas/widget.py")],
        "app/api/v1/widgets.py": [
            B(CH, 4, "# app/api/v1/widgets.py"),
            B(CH, 5, "# Allowed sort and filter fields — prevents SQL injection by allow-listing"),
        ],
        **auth_pkg(),
        "app/dependencies/api_key.py": [B(AM, 3, "# app/dependencies/api_key.py")],
        "app/dependencies/rate_limit.py": [B(AM, 4, "# app/dependencies/rate_limit.py")],
        "app/dependencies/rate_limit_redis.py": [B(AM, 5, "# app/dependencies/rate_limit_redis.py")],
        "app/middleware/cors.py": [B(AM, 6, "# app/middleware/cors.py")],
        "app/middleware/logging.py": [B(AM, 8, "# app/middleware/logging.py")],
        "app/main.py": [B(AM, 9, "# app/main.py")],
    }


UNITS.append(Unit(
    name="auth-middleware",
    own=[AM],
    files={
        **auth_app_files(),
        "tests/test_auth.py": [B(AM, 10, "# tests/test_auth.py")],
    },
    # no JWT_* variables: Settings takes the local/dev/test path (ephemeral key, per-env issuer/audience)
    env={"APP_ENV": "test"},
    pytest="run",
    smoke=smoke("smoke_auth_middleware.py"),
))

# --live only: RedisTenantRateLimiter shared by two uvicorn processes on Redis 7, against the in-process
# TenantRateLimiter in the same two processes. Same blocks as above (checked there), so it owns none.
UNITS.append(Unit(
    name="auth-middleware-shared-limit",
    own=[],
    files={
        **auth_app_files(),
        "harness_ratelimit_app.py": [S("ratelimit_app.py")],
        "tests/test_rate_limit_redis_live.py": [S("test_rate_limit_redis_live.py")],
    },
    live="run",
    pytest_args=["tests/test_rate_limit_redis_live.py"],
))

# ── crud-repository ────────────────────────────────────────────────────────────────────────────────
UNITS.append(Unit(
    name="crud-repository",
    own=[CR],
    files={
        **errors_pkg(),
        **domain_pkg(),
        **repository_pkg(),
        # harness-only: the repository must satisfy the service's WidgetRepository protocol
        "harness_protocol_check.py": [S("protocol_check_repository.py")],
    },
    typecheck=[
        "app/models/widget.py", "app/db/engine.py", "app/db/transaction.py",
        "app/repositories/widget.py", "app/repositories/widget_raw.py", "harness_protocol_check.py",
    ],
    imports=["app.models.widget", "app.db.engine", "app.db.transaction", "app.repositories.widget",
             "app.repositories.widget_raw"],
    smoke=smoke("smoke_repository.py"),
))

UNITS.append(Unit(
    name="crud-repository-test",
    own=[CRT],
    files={
        **errors_pkg(),
        **domain_pkg(),
        **repository_pkg(),
        "tests/repositories/conftest.py": [
            B(CRT, 0, "# tests/repositories/conftest.py"),
            B(CRT, 1, "# tests/repositories/conftest.py (continued)"),
        ],
        "tests/repositories/test_widget_repository.py": [
            B(CRT, 2, "# tests/repositories/test_widget_repository.py"),
            B(CRT, 3, "class TestCreate:"),
            B(CRT, 4, "class TestListCursorPagination:"),
            B(CRT, 5, "class TestSoftDeleteExclusion:"),
            B(CRT, 6, "class TestTenantIsolation:"),
            B(CRT, 7, "class TestOptimisticLocking:"),
            B(CRT, 8, "class TestFilters:"),
            B(CRT, 9, "class TestUniqueConstraints:"),
            B(CRT, 10, "class TestBatchOperations:"),
            B(CRT, 11, "class TestErrorMapping:"),
        ],
    },
    imports=[],
    pytest="collect",
    live="run",
))

# ── migrations (alembic offline mode runs env.py and every upgrade()/downgrade() without a DB) ──────
BATCH_REVISION = "alembic/versions/20260115_100400_harness_batch_backfill.py"
UNITS.append(Unit(
    name="migrations",
    own=[MG],
    files={
        **migration_files(),
        # "Large Table Batch Data Migration" is an alternative upgrade() body shown without its file
        # header. The harness gives it one, as the next revision, so offline SQL and --live run it too.
        BATCH_REVISION: [
            T('"""harness: the batch backfill from the doc, as a revision."""\n\n'
              'revision = "e5f6a7b8c9d0"\ndown_revision = "d4e5f6a7b8c9"\nbranch_labels = None\ndepends_on = None\n'),
            B(MG, 6, "# For tables > 100K rows, backfill in batches. Inside autocommit_block() every statement commits on its"),
            T("\n\ndef downgrade() -> None:  # harness: the fragment shows upgrade() only\n    pass"),
        ],
        "app/models/widget.py": [B(CR, 0, "# app/models/widget.py")],
        "app/db/rls.py": [B(MG, 7, "# app/db/rls.py")],
        "app/db/tenants.py": [B(MG, 8, "# app/db/tenants.py")],
        # + harness (--live): the batch backfill's locks read from pg_locks while a batch is paused, a
        # row the application holds during a batch, and the FORCE-toggle design it replaced. Appended to
        # the doc's module to share its session fixtures (one pair of roles per run).
        "tests/test_migrations.py": [B(MG, 9, "# tests/test_migrations.py"), S("test_harness_batch_backfill.py")],
        # pg_url for --live: the repository tests' testcontainers fixtures, where this test can see them
        "tests/conftest.py": [B(CRT, 0, "# tests/repositories/conftest.py")],
        "harness_offline_check.py": [S("offline_batch_refused.py")],
    },
    typecheck=[
        "alembic/env.py",
        "alembic/versions/20260115_095000_create_tenants_table.py",
        "alembic/versions/20260115_100000_create_widgets_table.py",
        "alembic/versions/20260115_100100_add_widget_categories.py",
        "alembic/versions/20260115_100200_seed_default_categories.py",
        "alembic/versions/20260115_100300_backfill_widget_category.py",
        BATCH_REVISION,
        "app/db/rls.py",
        "app/db/tenants.py",
        "tests/test_migrations.py",
    ],
    imports=["app.db.rls", "app.db.tenants"],
    pytest="collect",
    live="run",
    env={"DATABASE_URL": "postgresql+asyncpg://harness@localhost:5432/harness"},
    post=[
        # offline SQL for the whole chain the doc ships; the batched backfill has no --sql form, which
        # the last step checks: it fails with its own message after rendering everything before it
        ["{py}", "-m", "alembic", "-c", "alembic.ini", "upgrade", "d4e5f6a7b8c9", "--sql"],
        ["{py}", "-m", "alembic", "-c", "alembic.ini", "downgrade", "d4e5f6a7b8c9:base", "--sql"],
        ["{py}", "harness_offline_check.py"],
    ],
))

# ── dockerfile health endpoint ─────────────────────────────────────────────────────────────────────
UNITS.append(Unit(
    name="dockerfile-health",
    own=[DF],
    files={
        # readiness compares the database's revision with the newest migration the release ships
        **migration_files(),
        "app/models/widget.py": [B(CR, 0, "# app/models/widget.py")],
        "app/api/health.py": [B(DF, 0, "# app/api/health.py")],
        # --live: the schema-revision check against a real PostgreSQL (harness test)
        "tests/conftest.py": [B(CRT, 0, "# tests/repositories/conftest.py")],
        "tests/test_health_live.py": [S("test_health_live.py")],
    },
    typecheck=["app/api/health.py"],
    imports=["app.api.health"],
    env={"DATABASE_URL": "postgresql+asyncpg://harness@localhost:5432/harness"},
    live="run",
    pytest_args=["tests/test_health_live.py"],
    smoke=smoke("smoke_health.py"),
))

# ── gRPC (codegen from grpc-pattern.md's .proto blocks, then the Python servicer against it) ────────
GP = "grpc-pattern.md"
UNITS.append(Unit(
    name="grpc",
    own=[GR],
    files={
        **errors_pkg(),
        **domain_pkg(),
        **service_pkg(),
        **handler_request_id(),
        "proto/yourapp/v1/widget_service.proto": [MD(GP, "protobuf", 0, "// proto/yourapp/v1/widget_service.proto")],
        "proto/yourapp/v1/widget.proto": [MD(GP, "protobuf", 1, "// proto/yourapp/v1/widget.proto")],
        "proto/yourapp/v1/common.proto": [MD(GP, "protobuf", 2, "// proto/yourapp/v1/common.proto")],
        "harness_codegen.py": [S("grpc_codegen.py")],
        "app/grpc/widget_server.py": [B(GR, 0, "# app/grpc/widget_server.py")],
        "app/grpc/interceptors.py": [B(GR, 1, "# app/grpc/interceptors.py")],
        "app/grpc/context.py": [B(GR, 2, "# app/grpc/context.py")],
        "app/grpc/errors.py": [B(GR, 3, "# app/grpc/errors.py")],
        "app/grpc/server.py": [B(GR, 4, "# app/grpc/server.py")],
    },
    pre=[["{py}", "harness_codegen.py"]],
    env={"PYTHONPATH": "gen"},  # the generated modules import each other as yourapp.v1.*
    pyright={"extraPaths": ["gen"]},
    pyright_ignore=[(
        GR, '"aio" is unknown import symbol', "from grpc_health.v1.health import aio as health_aio",
        "grpc_health.v1.health exports `aio` (the asyncio HealthServicer) as public API; pyright 1.1.414 can't "
        "resolve the package's relative submodule import. smoke_grpc.py calls Health/Check on that servicer.",
    )],
    smoke=smoke("smoke_grpc.py"),
))

# ── observability (the app runs: lifespan → instrument_app, middleware, metrics read in-process) ─────
OBS_PRELUDE = T(
    "from app.context import RequestContext  # harness: names this fragment leaves to the reader\n"
    "from harness_stubs.orders import CircuitBreaker, CreateOrderRequest, Order, OrderModel, PaymentClient"
)
UNITS.append(Unit(
    name="observability",
    own=[OB],
    files={
        "harness_stubs/orders.py": [S("orders.py")],
        "app/config.py": [B(OB, 20, "# app/config.py")],
        "app/context.py": [B(OB, 21, "# app/context.py")],
        "app/dependencies.py": [B(OB, 22, "# app/dependencies.py")],
        "app/db.py": [S("obs_db.py")],
        "app/middleware/auth_middleware.py": [S("obs_auth_middleware.py")],
        "app/observability/tracing.py": [B(OB, 0, "# app/observability/tracing.py")],
        "app/observability/instruments.py": [B(OB, 1, "# app/observability/instruments.py")],
        "app/observability/sql_spans.py": [B(OB, 2, "# app/observability/sql_spans.py")],
        # --live: sql_spans.py on asyncpg against PostgreSQL (pg_url from the repository tests' conftest)
        "app/models/widget.py": [B(CR, 0, "# app/models/widget.py")],
        "tests/conftest.py": [B(CRT, 0, "# tests/repositories/conftest.py")],
        "tests/test_sql_spans_live.py": [S("test_sql_spans_live.py")],
        "app/observability/metrics.py": [B(OB, 6, "# app/observability/metrics.py")],
        "app/observability/app_metrics.py": [B(OB, 7, "# app/observability/app_metrics.py")],
        "app/observability/logging.py": [
            B(OB, 12, "# app/observability/logging.py"),
            B(OB, 13, "# app/observability/logging.py  (additional processor)"),
        ],
        "app/observability/logging_stdlib.py": [B(OB, 17, "# app/observability/logging_stdlib.py")],
        "app/observability/__init__.py": [B(OB, 18, "# app/observability/__init__.py")],
        "app/middleware/metrics_middleware.py": [B(OB, 8, "# app/middleware/metrics_middleware.py")],
        "app/middleware/db_metrics.py": [B(OB, 10, "# app/middleware/db_metrics.py")],
        "app/middleware/logging_middleware.py": [B(OB, 14, "# app/middleware/logging_middleware.py")],
        "app/main.py": [B(OB, 19, "# app/main.py")],
        "app/repositories/order_repository.py": [OBS_PRELUDE, B(OB, 4, "# app/repositories/order_repository.py")],
        "app/services/order_service.py": [
            OBS_PRELUDE,
            T("from app.repositories.order_repository import OrderRepository"),
            B(OB, 3, "# app/services/order_service.py"),
        ],
        "docs_fragments/propagation.py": [
            OBS_PRELUDE, B(OB, 5, "# OpenTelemetry handles context propagation within the same process via")],
        "docs_fragments/business_metrics.py": [
            OBS_PRELUDE,
            T("class _OrderServiceParts:  # harness: what the fragment's class has beyond this method\n"
              "    async def _process_order(self, ctx: RequestContext, req: CreateOrderRequest) -> Order: ..."),
            B(OB, 9, "# Inside service methods — record business-level metrics",
              subs=(("class OrderService:", "class OrderService(_OrderServiceParts):"),)),
        ],
        "docs_fragments/prometheus.py": [
            T("from fastapi import FastAPI  # harness: the app the fragment instruments\napp = FastAPI()"),
            B(OB, 11, "# app/main.py"),
        ],
        "docs_fragments/order_service_logging.py": [
            OBS_PRELUDE,
            T("from app.repositories.order_repository import OrderRepository\n"
              "class _OrderServiceParts:  # harness: the collaborator the fragment's class uses\n"
              "    _repo: OrderRepository"),
            B(OB, 15, "# app/services/order_service.py",
              subs=(("class OrderService:", "class OrderService(_OrderServiceParts):"),)),
        ],
        "docs_fragments/log_levels.py": [
            OBS_PRELUDE,
            T("import structlog\nlogger = structlog.get_logger()\norder: Order\nexc: Exception\n"
              "cb: CircuitBreaker\norder_id: str"),
            B(OB, 16, "# ERROR — actionable, needs investigation", wrap="def _fragment() -> None:"),
        ],
    },
    env={"DATABASE_URL": "postgresql+asyncpg://harness@localhost:5432/harness", "ENVIRONMENT": "local"},
    smoke=smoke("smoke_observability.py"),
    live="run",
    pytest_args=["tests/test_sql_spans_live.py"],
))

# ── performance (mostly fragments: each gets the app-level names it assumes from stubs/perf.py) ──────
PERF_PRELUDE = T("from harness_stubs.perf import *  # noqa: F403 — harness: names this fragment leaves to the reader")
# WRONG/CORRECT pairs define the same name twice on purpose
REDECL = T("# pyright: reportRedeclaration=false")
UNITS.append(Unit(
    name="performance",
    own=[PF],
    files={
        **errors_pkg(),
        "harness_stubs/orders.py": [S("orders.py")],
        "harness_stubs/perf.py": [S("perf.py")],
        "perf/event_loop.py": [REDECL, PERF_PRELUDE, B(PF, 0, "# ---- WRONG: blocks the event loop ----")],
        "perf/pools.py": [
            PERF_PRELUDE,
            B(PF, 1, "# ── asyncpg pool (used directly or via SQLAlchemy) ────────────────────"),
            B(PF, 2, "import asyncio"),  # 1.3 uses 1.2's _http_client
        ],
        "perf/parallel.py": [PERF_PRELUDE, B(PF, 3, "import asyncio")],
        "perf/streaming.py": [PERF_PRELUDE, B(PF, 4, "from fastapi import FastAPI")],
        "perf/slots.py": [REDECL, B(PF, 5, "from dataclasses import dataclass")],
        "perf/generators.py": [PERF_PRELUDE, B(PF, 6, "import asyncpg")],
        "perf/weakrefs.py": [B(PF, 7, "import weakref")],
        "perf/memory.py": [B(PF, 8, "import tracemalloc")],
        "perf/intermediate_lists.py": [REDECL, PERF_PRELUDE, B(PF, 9, "# ---- WRONG: creates 3 intermediate lists ----")],
        "app/db.py": [B(PF, 10, "# app/db.py")],
        "perf/eager_loading.py": [PERF_PRELUDE, B(PF, 11, "from collections.abc import Sequence")],
        "perf/bulk.py": [PERF_PRELUDE, B(PF, 12, "import asyncpg")],
        "perf/read_replicas.py": [PERF_PRELUDE, B(PF, 13, "# app/db.py")],
        "app/middleware/query_counter.py": [B(PF, 14, "# app/middleware/query_counter.py")],
        "perf/profiling.py": [B(PF, 15, "# ── Programmatic profiling for a specific code path ───────────────────")],
        "perf/tracemalloc_compare.py": [B(PF, 16, "# Already covered in Section 2.4 — use for debugging memory leaks.")],
        "perf/asyncio_debug.py": [PERF_PRELUDE, B(PF, 17, "# Enable via environment variable (recommended for development)")],
        "perf/line_profiling.py": [PERF_PRELUDE, B(PF, 18, "# Decorate the function you want to profile")],
        "tests/benchmarks/test_order_performance.py": [
            PERF_PRELUDE, B(PF, 19, "# tests/benchmarks/test_order_performance.py")],
        "app/cache/redis_cache.py": [
            PERF_PRELUDE,
            T("class _OrderServiceParts:  # harness: the collaborators the fragment's class uses\n"
              "    _cache: \"RedisCache\"\n    _repo: OrderRepo"),
            B(PF, 20, "# app/cache/redis_cache.py",
              subs=(("class OrderService:", "class OrderService(_OrderServiceParts):"),)),
        ],
        "perf/inprocess_cache.py": [PERF_PRELUDE, B(PF, 21, "import json")],
        "app/cache/single_flight.py": [
            PERF_PRELUDE,
            T("from app.cache.redis_cache import RedisCache\n"
              "class _OrderServiceParts:  # harness: the collaborators the fragment's class uses\n"
              "    _cache: RedisCache\n    _repo: OrderRepo"),
            B(PF, 22, "# app/cache/single_flight.py",
              subs=(("class OrderService:", "class OrderService(_OrderServiceParts):"),)),
        ],
        "perf/serialization.py": [B(PF, 23, "import json")],
        "perf/gil.py": [B(PF, 24, "from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor")],
        "perf/io_bound.py": [B(PF, 25, "# For IO-bound work (HTTP calls, DB queries, file IO), asyncio releases")],
        "perf/celery_vs_processes.py": [
            PERF_PRELUDE, B(PF, 26, "# ── ProcessPoolExecutor — use for short CPU tasks within a request ────")],
        "perf/uvloop_setup.py": [
            PERF_PRELUDE, B(PF, 27, "# uvloop is a drop-in replacement for asyncio's event loop, written in Cython.")],
    },
    typecheck=None,
    env={"DATABASE_URL": "postgresql+asyncpg://harness@localhost:5432/harness",
         "DATABASE_REPLICA_URL": "postgresql+asyncpg://harness@localhost:5432/harness"},
    pytest="collect",
    pytest_args=["-p", "pytest_benchmark", "tests/benchmarks"],
    pyright_ignore=[(
        PF, 'Type "Unknown | None" is not assignable to return type "bytes"',
        "return msgpack.packb(self.model_dump(), use_bin_type=True)",
        "msgpack ships no type hints; pyright infers packb() from its pure-Python fallback, where "
        "Packer.pack() returns None only with autoreset=False. smoke_performance.py round-trips to_cache().",
    )],
    smoke=smoke("smoke_performance.py"),
))

# ── websocket (two real clients against the FastAPI endpoint; the Channels consumer under Django) ────
UNITS.append(Unit(
    name="websocket",
    own=[WS],
    files={
        **errors_pkg(),
        **auth_pkg(),  # the ticket endpoint uses auth-middleware-python.md's bearer dependency
        "app/ws/manager.py": [B(WS, 0, "# app/ws/manager.py")],
        "app/ws/tickets.py": [B(WS, 1, "# app/ws/tickets.py")],
        "app/ws/endpoint.py": [B(WS, 2, "# app/ws/endpoint.py")],
        "app/ws/handlers.py": [B(WS, 3, "# app/ws/handlers.py")],
        "app/ws/heartbeat.py": [B(WS, 8, "# app/ws/heartbeat.py")],
        "app/main.py": [B(WS, 9, "# app/main.py")],
        "myapp/tickets.py": [B(WS, 4, "# myapp/tickets.py")],
        "myapp/consumers.py": [B(WS, 5, "# myapp/consumers.py")],
        "myapp/routing.py": [B(WS, 6, "# myapp/routing.py")],
        "myapp/asgi.py": [B(WS, 7, "# myapp/asgi.py")],
        "harness_django_settings.py": [S("django_settings.py")],
        # --live: RedisTicketStore and myapp/tickets.py on Redis 7, through the Channels application
        "tests/test_ws_tickets_live.py": [S("test_ws_tickets_live.py")],
    },
    typecheck=["app/ws/manager.py", "app/ws/tickets.py", "app/ws/endpoint.py", "app/ws/handlers.py",
               "app/ws/heartbeat.py", "app/main.py", "myapp/tickets.py", "myapp/consumers.py",
               "myapp/routing.py", "myapp/asgi.py"],
    imports=["app.ws.manager", "app.ws.tickets", "app.ws.endpoint", "app.ws.handlers", "app.ws.heartbeat",
             "app.main"],
    # REDIS_URL: the lifespan builds the client (lazy; nothing connects); the smoke overrides the store
    # ALLOWED_ORIGINS for the Django settings; the FastAPI Settings gets the same list from its APP_ENV=test
    # default
    env={"DJANGO_SETTINGS_MODULE": "harness_django_settings", "APP_ENV": "test",
         "REDIS_URL": "redis://127.0.0.1:1/0", "ALLOWED_ORIGINS": '["http://localhost:3000"]'},
    live="run",
    pytest_args=["tests/test_ws_tickets_live.py"],
    smoke=smoke("smoke_websocket.py"),
    pyright_ignore=[(
        WS, 'Argument of type "list[URLResolver | URLPattern]" cannot be assigned to parameter "routes"',
        '"websocket": BrowserOriginValidator(URLRouter(websocket_urlpatterns), settings.ALLOWED_ORIGINS),',
        "Channels' documented routing (URLRouter over re_path() patterns). pyright's bundled typeshed stub "
        "for channels types `routes` as list[_ExtendedURLPattern | URLRouter], a type_check_only subclass "
        "re_path() can't return. smoke_websocket.py and the --live test route handshakes through this "
        "URLRouter to the consumer.",
    )],
))

# ── worker (Celery task applied in-process, dramatiq actor fn, asyncio worker, APScheduler, health) ──
UNITS.append(Unit(
    name="worker",
    own=[WK],
    files={
        "app/services/email.py": [S("worker_services.py")],
        "app/services/idempotency.py": [T("from app.services.email import IdempotencyStore  # harness stand-in")],
        "app/worker/celery_app.py": [B(WK, 0, "# app/worker/celery_app.py")],
        "app/config/celery_config.py": [B(WK, 1, "# app/config/celery_config.py")],
        "app/tasks/email.py": [B(WK, 2, "# app/tasks/email.py")],
        "app/tasks/email_dramatiq.py": [B(WK, 3, "# app/tasks/email_dramatiq.py")],
        "app/worker/async_worker.py": [B(WK, 4, "# app/worker/async_worker.py")],
        "app/worker/scheduler.py": [B(WK, 5, "# app/worker/scheduler.py")],
        "app/worker/health.py": [
            B(WK, 6, "# app/worker/health.py"),
            T("\n\ndef get_worker_health() -> WorkerHealth:  # harness: the doc leaves resolving this to the app\n"
              "    return WorkerHealth(queue_connected=True, last_job_at=None, in_flight=0, max_concurrency=5)"),
        ],
        "app/services/job_producer.py": [B(WK, 7, "# app/services/job_producer.py")],
    },
    smoke=smoke("smoke_worker.py"),
))


# ── packs outside backend/archetypes: units_packs.py (keep this block LAST; it imports the names above) ──
from units_packs import COMMENT_ONLY as _PACKS_COMMENT_ONLY  # noqa: E402
from units_packs import EXPECTED as _PACKS_EXPECTED  # noqa: E402
from units_packs import SKIPS as _PACKS_SKIPS  # noqa: E402
from units_packs import UNITS as _PACKS_UNITS  # noqa: E402

UNITS.extend(_PACKS_UNITS)
EXPECTED.update(_PACKS_EXPECTED)
COMMENT_ONLY.extend(_PACKS_COMMENT_ONLY)
SKIPS.update(_PACKS_SKIPS)
