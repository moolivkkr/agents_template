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

from units import CH, B, S, T, Unit, errors_pkg

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


def django_ignores(md: str, proof: str) -> list[tuple[str, str, str, str]]:
    """The two pyright false positives every Django model sample hits. Django ships no type information,
    so pyright infers from its source: it can't see the `objects` manager the model metaclass adds, and it
    types a field's `default=` parameter from Django's NOT_PROVIDED sentinel. (django-stubs would fix both,
    but installed next to the archetypes it rejects websocket-pattern-python.md's Channels routing.) Each
    is proven at runtime by the unit's smoke/tests, which run those lines against a real database."""
    why = f"Django adds this at runtime (no type information for pyright); {proof} runs it on SQLite."
    return [
        (md, 'Cannot access attribute "objects" for class "type[', ".objects", why),
        *[(md, f'Argument of type "{lit}" cannot be assigned to parameter "default" of type "type[NOT_PROVIDED]"',
           "default=", why)
          for lit in ("Literal[True]", "Literal[False]", "Literal[1]", "Literal[0]", "Literal['']")],
    ]

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

# ── infrastructure/localstack-aws-local.md: client factory; S3, KMS and SQS over HTTP (moto server) ────
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

# ── testing/property-based.md: the properties run under real Hypothesis ───────────────────────────────
UNITS.append(Unit(
    name="pack-property-based",
    own=[PB],
    files={
        "harness_stubs/props.py": [stub("props.py")],
        "tests/test_properties.py": [
            T("from harness_stubs.props import (  # harness: the app functions and model under test\n"
              "    ParseError, Widget, decode, encode, is_valid_email, normalize_email, parse,\n)"),
            B(PB, 0, "from hypothesis import given, strategies as st, settings, assume"),
        ],
    },
    pytest="run",
))

# ── testing/external-service-mocks.md: the pytest-httpx fixtures, each used by a test ──────────────────
UNITS.append(Unit(
    name="pack-external-service-mocks",
    own=[EM],
    files={
        "tests/conftest.py": [stub("payments_conftest.py")],
        "tests/test_external_mocks.py": [
            T("import re  # harness: the S3 fixture's regex URLs (the doc shows the fixtures without imports)"),
            B(EM, 0, "import pytest"),
            B(EM, 1, "@pytest.fixture"),
            B(EM, 2, "@pytest.fixture"),
            stub("test_mocks_harness.py"),
        ],
    },
    pytest="run",
    pytest_args=["-o", "asyncio_mode=auto"],  # the doc's async test has no marker (testing/pytest.md: auto)
))

# ── testing/contract-testing.md: a real Pact V4 mock provider (pact-python 3, Rust FFI, localhost) ──────
UNITS.append(Unit(
    name="pack-contract-testing",
    own=[CT],
    files={
        "harness_stubs/widget_client.py": [stub("widget_client.py")],
        "tests/test_widget_contract.py": [
            T("from harness_stubs.widget_client import WidgetClient  # harness: the consumer's API client"),
            B(CT, 0, "from pact import Pact, match  # pact-python 3 (the Consumer/Provider API is the deprecated "
                     "pact.v2)"),
        ],
    },
    pytest="run",
    post=[["{py}", "-c",
           "import json; d = json.load(open('pacts/widget-dashboard-widget-service.json'))\n"
           "(i,) = d['interactions']\n"
           "assert d['metadata']['pactSpecification']['version'].startswith('4'), d['metadata']\n"
           "assert i['request']['path'] == '/api/v1/widgets/abc-123', i['request']\n"
           "body = i['response']['body']['content']\n"
           "assert set(body) == {'data', 'meta'}, body\n"
           "assert '$.data.name' in i['response']['matchingRules']['body'], i['response']['matchingRules']\n"
           "print('pact file: 1 interaction, envelope body with type matchers')"]],
))

# ── testing/load-testing.md: the locustfile, run headless by real locust against a local stand-in API ──
UNITS.append(Unit(
    name="pack-load-testing",
    own=[LT],
    files={
        "locustfile.py": [B(LT, 0, "import os")],
        "harness_run_locust.py": [stub("run_locust.py")],
    },
    imports=["locustfile"],
    env={"APP_BASE_URL": "http://127.0.0.1:1"},  # read at class definition; the post step sets the real one
    post=[["{py}", "harness_run_locust.py"]],
))

# ── testing/test-case-traceability.md: TC-named tests against a small orders API ───────────────────────
UNITS.append(Unit(
    name="pack-test-case-traceability",
    own=[TT],
    files={
        "harness_stubs/order_helpers.py": [stub("order_helpers.py")],
        "tests/conftest.py": [stub("orders_conftest.py")],
        "tests/test_orders_tc.py": [
            T("import pytest\n\nfrom tests.conftest import VALID_ORDER, auth  # harness: the suite's helpers"),
            B(TT, 0, '@pytest.mark.parametrize("token,status", ['),
        ],
        "docs_fragments/test_change.py": [
            T("from httpx import Response\n\n"
              "from harness_stubs.order_helpers import assert_order_envelope  # harness: tests/helpers.py"),
            B(TT, 1, "# TEST-CHANGE 2026-09-30 phase 3: envelope checks moved into a shared helper, same "
                     "assertions (moved: tests/helpers.py:40)",
              wrap="def _fragment(resp: Response) -> None:"),
        ],
    },
    imports=["docs_fragments.test_change"],
    smoke=smoke("smoke_test_change.py"),
    pytest="run",
    pytest_args=["tests/test_orders_tc.py"],
))

# ── frameworks/graphql.md: the Strawberry Query/Widget types in a real schema, executed ────────────────
UNITS.append(Unit(
    name="pack-graphql",
    own=[GQ],
    files={
        "harness_stubs/strawberry_app.py": [stub("strawberry_app.py")],
        "app/auth/context.py": [T("from harness_stubs.strawberry_app import get_current_user  # noqa: F401")],
        "app/graphql/dataloaders.py": [
            T("from harness_stubs.strawberry_app import TagLoader, UserLoader  # noqa: F401")],
        "app/graphql/schema.py": [
            T("from harness_stubs.strawberry_app import Tag, User, WidgetConnection, WidgetFilter, WidgetStatus  "
              "# harness: the schema's other types"),
            B(GQ, 0, "# app/graphql/schema.py"),
        ],
    },
    smoke=smoke("smoke_graphql.py"),
))

# ── frameworks/fastapi.md: main.py + router + DI + models + handler as one app, run through TestClient ──
# The envelope models and the request-id middleware are the crud-handler archetype's own blocks.
UNITS.append(Unit(
    name="pack-fastapi",
    own=[FA],
    files={
        **errors_pkg(),
        "app/schemas/base.py": [B(CH, 0, "# app/schemas/base.py")],
        "app/middleware/request_id.py": [B(CH, 3, "# app/middleware/request_id.py")],
        "harness_stubs/fastapi_app.py": [stub("fastapi_app.py")],
        "users/schemas.py": [
            T("from datetime import datetime\nfrom uuid import UUID\n\n"
              "from pydantic import BaseModel, ConfigDict, EmailStr, Field"),
            B(FA, 3, "class CreateUserRequest(BaseModel):"),
        ],
        "users/deps.py": [
            T("from collections.abc import AsyncGenerator\nfrom typing import Annotated\n\n"
              "from fastapi import Depends\nfrom sqlalchemy.ext.asyncio import AsyncSession\n\n"
              "from harness_stubs.fastapi_app import SessionLocal, UserRepository, UserService"),
            B(FA, 2, "async def get_db() -> AsyncGenerator[AsyncSession, None]:"),
        ],
        "users/router.py": [
            T("from typing import Annotated\nfrom uuid import UUID\n\nfrom fastapi import APIRouter, Depends, Request\n\n"
              "from app.schemas.base import Envelope, Meta\n"
              "from harness_stubs.fastapi_app import User, UserService, require_auth\n"
              "from users.deps import get_user_service\nfrom users.schemas import UserResponse"),
            B(FA, 1, "# users/router.py"),
        ],
        "main.py": [
            T("from harness_stubs.fastapi_app import auth, db\n"
              "from users import router as users  # users/router.py: the module whose `router` main.py includes"),
            B(FA, 0, "# main.py"),
        ],
        "errors_handler.py": [
            T("from fastapi import Request\nfrom fastapi.responses import JSONResponse\n\n"
              "from harness_stubs.fastapi_app import UserNotFoundError\nfrom main import app"),
            B(FA, 4, "@app.exception_handler(UserNotFoundError)"),
        ],
    },
    smoke=smoke("smoke_fastapi.py"),
))

# ── frameworks/django.md: model + serializer + ViewSet in a Django project on SQLite (DRF APIClient) ──
# The query-optimization fragment uses a User with a profile, groups and a department: the reader's
# model (stubs/packs/directory_models.py), not the Models section's.
UNITS.append(Unit(
    name="pack-django",
    own=[DJ],
    files={
        "harness_django_settings.py": [stub("django_pack_settings.py")],
        "harness_urls.py": [stub("django_pack_urls.py")],
        "harness_pagination.py": [T(
            "from rest_framework.pagination import CursorPagination\n\n\n"
            "class NewestFirstCursorPagination(CursorPagination):  # harness: the project's list paginator\n"
            '    ordering = "-created_at"\n    page_size = 20')],
        "myapp/models.py": [
            T("from django.db import models"),
            B(DJ, 0, "class User(models.Model):"),
            T("\n\nclass Profile(models.Model):  # harness: the relation the ViewSet's select_related('profile') reads\n"
              "    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name=\"profile\")"),
        ],
        "myapp/serializers.py": [
            T("from rest_framework import serializers\n\nfrom myapp.models import User"),
            B(DJ, 1, "class UserSerializer(serializers.ModelSerializer):"),
        ],
        "myapp/views.py": [
            T("from rest_framework import viewsets\nfrom rest_framework.permissions import IsAuthenticated\n\n"
              "from myapp.models import User\nfrom myapp.serializers import UserSerializer"),
            B(DJ, 2, "class UserViewSet(viewsets.ModelViewSet):"),
        ],
        "directory/models.py": [stub("directory_models.py")],
        "directory/queries.py": [
            T("from django.db.models import Count\n\nfrom directory.models import User"),
            B(DJ, 3, "# Always use select_related (FK) and prefetch_related (M2M/reverse FK)"),
        ],
    },
    imports=[],  # Django models import only after django.setup(): the smoke imports them
    env={"DJANGO_SETTINGS_MODULE": "harness_django_settings"},
    pyright_ignore=django_ignores(DJ, "smoke_django.py"),
    smoke=smoke("smoke_django.py"),
))
