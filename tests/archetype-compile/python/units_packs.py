"""Units for the ```python blocks OUTSIDE .claude/skills/backend/archetypes (languages/, frameworks/,
testing/, databases/, infrastructure/, core/ ...). units.py merges this module's UNITS, EXPECTED,
COMMENT_ONLY and SKIPS at its very end; import units (never this module first).

Same model and rules as units.py: a block is referenced as (file key, 0-based index among the file's
```python blocks, anchor = its first non-empty line); a pack file's key is its path relative to
.claude/skills. Units are assembled from the REAL blocks; stubs/packs/ holds only the app-level names a
fragment leaves to the reader (a model, a settings object, a fixture), never the library a sample
demonstrates. Where a sample is a fragment (a method, statements with a bare `await` or `return`), the
harness gives it the enclosing function or class (B.wrap / B.subs) and the names it uses as parameters or
harness text (T). Archetype blocks are reused where a pack sample builds on them (testing/pytest.md's
tests run against the real crud-service archetype).
"""
from __future__ import annotations

from pathlib import Path

from units import B, S, T, Unit

_HERE = Path(__file__).parent


def smoke(name: str) -> str:
    """A smoke script from smoke/packs/."""
    return (_HERE / "smoke" / "packs" / name).read_text(encoding="utf-8")


def stub(name: str) -> S:
    """A harness file from stubs/packs/."""
    return S(f"packs/{name}")


LIVE = stub("live_containers.py")  # --live fixtures: pg_dsn (PostgreSQL 16), redis_url (Redis 7)

# ── file keys ──────────────────────────────────────────────────────────────────────────────────────
SO = "core/security-owasp.md"
TP = "core/testing-principles.md"
DD = "databases/dynamodb.md"
RD = "databases/redis.md"
SQ = "databases/sqlite.md"
DJ = "frameworks/django.md"
DR = "frameworks/drf.md"
FA = "frameworks/fastapi.md"
GQ = "frameworks/graphql.md"
LS = "infrastructure/localstack-aws-local.md"
ST = "infrastructure/saas-tenancy-models.md"
PY = "languages/python.md"
CT = "testing/contract-testing.md"
EM = "testing/external-service-mocks.md"
LT = "testing/load-testing.md"
PB = "testing/property-based.md"
PT = "testing/pytest.md"
TT = "testing/test-case-traceability.md"

EXPECTED = {
    SO: 1, TP: 2, DD: 1, RD: 3, SQ: 1, DJ: 4, DR: 9, FA: 5, GQ: 1, LS: 1, ST: 1, PY: 28,
    CT: 1, EM: 3, LT: 1, PB: 1, PT: 6, TT: 2,
}

# Blocks that hold only comments (verified by the harness).
COMMENT_ONLY: list[tuple[str, int, str]] = []

# (file, index, anchor) -> reason. Keep empty unless a block truly can't be checked.
SKIPS: dict[tuple[str, int, str], str] = {}

UNITS: list[Unit] = []

AWS_ENV = {"AWS_DEFAULT_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing"}

# ── core/security-owasp.md: the WRONG/RIGHT pair, through psycopg 3 against PostgreSQL (--live) ────────
UNITS.append(Unit(
    name="pack-security-owasp",
    own=[SO],
    files={
        "docs_fragments/sql_injection.py": [
            T("import psycopg"),
            B(SO, 0, "# WRONG", wrap="def query_user(cursor: psycopg.Cursor, user_id: str) -> None:"),
        ],
        "tests/conftest.py": [LIVE],
        "tests/test_sql_injection_live.py": [stub("test_sql_injection_live.py")],
    },
    pytest="collect",
    live="run",
    pyright_ignore=[
        (SO, prefix, 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
         "the block's WRONG line: psycopg 3 types `query` as LiteralString | Template | SQL, so pyright "
         "rejects the f-string, which is the point the block makes. The call is valid at runtime: "
         "test_sql_injection_live.py runs it against PostgreSQL (--live) and shows the spliced input "
         "matching every row.")
        for prefix in ('No overloads for "execute" match the provided arguments',
                       'Argument of type "str" cannot be assigned to parameter "query"')
    ],
))

# ── core/testing-principles.md: both tests run against the domain names they leave to the reader ─────
UNITS.append(Unit(
    name="pack-testing-principles",
    own=[TP],
    files={
        "harness_stubs/principles.py": [stub("principles.py")],
        "tests/test_principles.py": [
            T("from harness_stubs.principles import Discount, Item, Order, User  # harness: the app's names"),
            B(TP, 0, "def test_apply_discount_reduces_order_total():"),
            B(TP, 1, "# Factory pattern"),
        ],
    },
    pytest="run",
))

# ── databases/redis.md: real redis-py; each fragment in the function it implies; --live: Redis 7 ──────
UNITS.append(Unit(
    name="pack-redis",
    own=[RD],
    files={
        "harness_stubs/redis_app.py": [stub("redis_app.py")],
        "app/cache_aside.py": [
            T("from redis import Redis\n\nfrom harness_stubs.redis_app import Db, deserialize, serialize"),
            B(RD, 0, "# Read", wrap="def get_or_load(redis: Redis, db: Db, key: str, ttl_seconds: int) -> object:"),
        ],
        "app/sessions.py": [
            T("import json\n\nfrom redis import Redis\n\nfrom harness_stubs.redis_app import SESSION_TTL_SECONDS, User"),
            B(RD, 1, "redis.set(", wrap="def store_session(redis: Redis, token: str, user: User) -> None:"),
        ],
        "app/pool.py": [
            T('import os\n\nimport redis\n\nREDIS_URL = os.environ["REDIS_URL"]  # harness: the app\'s setting'),
            B(RD, 2, "# Always use connection pool — never single connection"),
        ],
        "tests/conftest.py": [LIVE],
        "tests/test_redis_live.py": [stub("test_redis_live.py")],
    },
    env={"REDIS_URL": "redis://127.0.0.1:1/0"},  # import builds the pool lazily; nothing connects
    smoke=smoke("smoke_redis.py"),
    pytest="collect",
    live="run",
))

# ── databases/sqlite.md: the in-memory fixture, used by two harness tests ────────────────────────────
UNITS.append(Unit(
    name="pack-sqlite",
    own=[SQ],
    files={
        "harness_stubs/sqlite_models.py": [stub("sqlite_models.py")],
        "tests/test_sqlite_fixture.py": [
            T("import pytest\nfrom sqlalchemy import create_engine\n\n"
              "from harness_stubs.sqlite_models import Base  # harness: the app's declarative base"),
            B(SQ, 0, "# In-memory DB per test — zero cleanup needed"),
            stub("test_sqlite_harness.py"),
        ],
    },
    pytest="run",
))

# ── infrastructure/saas-tenancy-models.md: the repository method, in its class, on SQLite ────────────
UNITS.append(Unit(
    name="pack-saas-tenancy",
    own=[ST],
    files={
        "harness_stubs/tenancy_models.py": [stub("tenancy_models.py")],
        "app/resources.py": [
            T("from uuid import UUID\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\n"
              "from harness_stubs.tenancy_models import Resource\n\n\n"
              "class _RepositoryParts:  # harness: the class the fragment's method belongs to\n"
              "    session: Session"),
            B(ST, 0, "# Python example (SQLAlchemy 2.0 select(); Session.query() is the legacy API)",
              wrap="class ResourceRepository(_RepositoryParts):"),
        ],
    },
    smoke=smoke("smoke_saas_tenancy.py"),
))

# ── databases/dynamodb.md: boto3 against moto in-process (smoke) and over HTTP (moto's server mode) ───
AWS_UNIT_FILES = {
    "harness_stubs/dynamo.py": [stub("dynamo.py")],
    "tests/conftest.py": [stub("aws_endpoint.py")],
    "tests/test_aws_endpoint.py": [stub("test_aws_endpoint.py")],
}
UNITS.append(Unit(
    name="pack-dynamodb",
    own=[DD],
    files={
        **AWS_UNIT_FILES,
        "app/widgets_dynamo.py": [
            T("from harness_stubs.dynamo import tenant_id, widget  # harness: the values the fragment uses"),
            B(DD, 0, "import boto3"),
        ],
    },
    imports=[],  # the fragment calls DynamoDB at import: the smoke imports it inside moto
    env=AWS_ENV,
    smoke=smoke("smoke_dynamodb.py"),
    pytest="run",
    pytest_args=["tests/test_aws_endpoint.py", "-k", "dynamodb"],
))

# ── infrastructure/localstack-aws-local.md: client factory; --live: S3, KMS and SQS on LocalStack ─────
UNITS.append(Unit(
    name="pack-localstack",
    own=[LS],
    files={
        **AWS_UNIT_FILES,
        "app/aws_clients.py": [B(LS, 0, "import boto3")],
    },
    env=AWS_ENV,
    pyright_ignore=[
        (LS, prefix, "return boto3.client(**kwargs)",
         "types-boto3 overloads boto3.client() on a Literal service name, so a factory taking the name as a "
         "str (and the kwargs as a dict) matches no overload. boto3 accepts it: smoke_localstack.py builds "
         "the s3/kms/sqs clients through it with and without AWS_ENDPOINT_URL, and test_aws_endpoint.py "
         "uses them over HTTP against a local endpoint.")
        for prefix in ('No overloads for "client" match the provided arguments',
                       'Argument of type "str" cannot be assigned to parameter "service_name"',
                       'Argument of type "str" cannot be assigned to parameter "use_ssl"',
                       'Argument of type "str" cannot be assigned to parameter "config"')
    ],
    smoke=smoke("smoke_localstack.py"),
    pytest="run",
    pytest_args=["tests/test_aws_endpoint.py", "-k", "localstack"],
))
