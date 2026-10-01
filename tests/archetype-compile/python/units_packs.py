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

from units import CH, B, S, T, Unit, domain_pkg, errors_pkg, handler_pkg, repository_pkg, service_pkg

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
    SO: 1, TP: 2, DD: 1, RD: 3, SQ: 1, DJ: 4, DR: 10, FA: 5, GQ: 1, LS: 1, ST: 1, PY: 28,
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

# ── frameworks/drf.md: every block in one Django project on SQLite; the doc's APITestCase suite and the
# harness's request tests run under Django's own test runner (post step) ─────────────────────────────
DRF_SERVICE_SUBS = (("class WidgetService:", "class WidgetService(_WidgetServiceParts):"),)
UNITS.append(Unit(
    name="pack-drf",
    own=[DR],
    files={
        "config/settings.py": [stub("drf_settings_base.py"), B(DR, 4, "# settings.py")],
        "config/urls.py": [stub("drf_urls.py")],
        "config/middleware.py": [stub("drf_middleware.py")],
        "apps/users/models.py": [stub("drf_users_models.py")],
        "apps/users/serializers.py": [
            B(DR, 5, "# apps/users/serializers.py — custom JWT claims (never import DRF serializers from settings.py)")],
        "apps/widgets/models.py": [stub("drf_widgets_models.py")],
        "apps/core/exceptions.py": [B(DR, 6, "# apps/core/exceptions.py")],
        "apps/core/renderers.py": [
            B(DR, 7, '# apps/core/renderers.py — wraps every success body as {"data": ..., "meta": {"request_id": ...}}.')],
        "apps/widgets/filters.py": [
            T("from apps.widgets.models import Widget  # harness: the app's model"),
            B(DR, 3, "from urllib.parse import parse_qs, urlparse"),
        ],
        # the doc's block holds the FilterSet and apps/core/pagination.py's paginator together
        "apps/core/pagination.py": [T("from apps.widgets.filters import EnvelopeCursorPagination  # noqa: F401")],
        "apps/widgets/serializers.py": [B(DR, 0, "from rest_framework import serializers")],
        "apps/widgets/permissions.py": [B(DR, 2, "from rest_framework.permissions import BasePermission")],
        "apps/widgets/service_parts.py": [stub("drf_service_parts.py")],
        "apps/widgets/services.py": [
            T("from apps.widgets.models import AuditLog, Widget\n"
              "from apps.widgets.service_parts import NotificationService, _WidgetServiceParts  # harness"),
            B(DR, 9, "# PREFER: Explicit service calls — predictable, testable, traceable", subs=DRF_SERVICE_SUBS),
        ],
        "apps/widgets/views.py": [
            T("from rest_framework.permissions import IsAuthenticated\n\n"
              "from apps.core.pagination import EnvelopeCursorPagination\n"
              "from apps.widgets.filters import WidgetFilterSet\n"
              "from apps.widgets.models import Widget\n"
              "from apps.widgets.permissions import IsTenantMember\n"
              "from apps.widgets.serializers import CreateWidgetSerializer, UpdateWidgetSerializer, WidgetSerializer\n"
              "from apps.widgets.services import WidgetService"),
            B(DR, 1, "from rest_framework import viewsets, status"),
        ],
        "tests/factories.py": [stub("drf_factories.py")],
        "tests/test_widgets.py": [
            T("from uuid import uuid4\n\nfrom apps.widgets.models import Widget\n"
              "from tests.factories import UserFactory, WidgetFactory  # harness: the suite's factories"),
            B(DR, 8, "from rest_framework.test import APITestCase, APIClient"),
        ],
        "tests/test_drf_harness.py": [stub("test_drf_harness.py")],
    },
    imports=[],  # Django modules import only after django.setup(): the smoke imports them
    env={"DJANGO_SETTINGS_MODULE": "config.settings", "JWT_SIGNING_KEY": "harness-only-signing-key-0123456789abcdef",
         "JWT_ISSUER": "widget-api-test", "JWT_AUDIENCE": "widget-api-test"},
    pyright_ignore=[
        *django_ignores(DR, "the post step's test suite"),
        (DR, 'Method "get_serializer_class" overrides class "GenericAPIView" in an incompatible manner',
         "def get_serializer_class(self):",
         "DRF ships no type information: pyright infers GenericAPIView.get_serializer_class() as Never from "
         "`assert self.serializer_class is not None` on its `serializer_class = None`. The post step's "
         "tests create, update and list through each serializer it returns."),
        *[(DR, f'Cannot access attribute "{attr}" for class "WSGIRequest"', "response.",
           "Django's test client has no type information: pyright infers its request() result as the "
           "WSGIRequest it builds, not the response it returns. The post step runs these assertions.")
          for attr in ("status_code", "json")],
        (DR, 'Method "has_permission" overrides class "BasePermission" in an incompatible manner',
         "def has_permission(self, request, view):",
         "DRF ships no type information: pyright infers BasePermission.has_permission() as Literal[True] from "
         "its `return True`. test_drf_harness.py runs all three permissions both ways (IsTenantMember through "
         "the ViewSet, HasPermission and IsAdminOrReadOnly through probe views)."),
        (DR, 'Method "to_representation" overrides class "Serializer" in an incompatible manner',
         "def to_representation(self, instance):",
         "pyright infers Serializer.to_representation()'s return from DRF's untyped source (an OrderedDict "
         "built in the body); the override returns the read serializer's .data. The create and update "
         "tests check the 201/200 bodies are the read shape."),
        (DR, 'Cannot assign to attribute "enveloped" for class "Response"', "response.enveloped = True",
         "a plain instance attribute on DRF's Response (no type information declares it). The cursor-page "
         "tests read list bodies the renderer passed through unwrapped because of it."),
    ],
    smoke=smoke("smoke_drf.py"),
    post=[["{py}", "-m", "django", "test", "tests", "--noinput", "-v", "2"]],
))

# ── testing/pytest.md: the doc's tests against the REAL crud-service / crud-repository / error-handling
# archetypes (in-memory implementations of the service's protocols; PostgreSQL 16 with --live) ────────
def pytest_pack_files() -> dict[str, list[B | T | S]]:
    return {
        **errors_pkg(), **domain_pkg(), **service_pkg(), **handler_pkg(), **repository_pkg(),
        "harness_stubs/pytest_pack.py": [stub("pytest_pack.py")],
        "tests/conftest.py": [B(PT, 0, "import pytest"), stub("pytest_pack_conftest.py")],
        "tests/test_parametrize.py": [
            T("from app.errors import ValidationFailedError\n"
              "from harness_stubs.pytest_pack import TID, UID  # harness: the suite's ids"),
            B(PT, 1, "import pytest"),
        ],
        "tests/test_mocking.py": [
            T("import pytest\n\nfrom app.errors import ConflictError\n"
              "from app.services.protocols import AuditWriter, Cache, WidgetRepository\n"
              "from app.services.widget import WidgetService\n"
              "from harness_stubs.pytest_pack import TID, UID, WID  # harness: the suite's ids"),
            B(PT, 3, "import json"),
        ],
        "tests/test_pytest_harness.py": [stub("test_pytest_harness.py")],
        "tests/db/conftest.py": [
            T("from app.models.widget import Base\nfrom app.repositories.widget import WidgetRepository"),
            B(PT, 4, "from collections.abc import AsyncIterator"),
        ],
        "tests/db/test_async_patterns.py": [
            T("from harness_stubs.pytest_pack import SomeModel, some_model  # harness: the doc's placeholders"),
            B(PT, 2, "# pyproject.toml"),
        ],
        "tests/db/test_db_fixtures_live.py": [stub("test_pytest_db_live.py")],
        "docs_fragments/assertions.py": [
            T("from typing import Any\n\nfrom app.domain.widget import Widget\n"
              "from app.services.widget import WidgetService\n"
              "from harness_stubs.pytest_pack import MISSING_ID, TID, UID, WID"),
            B(PT, 5, "import pytest",
              wrap="async def _fragment(svc: WidgetService, result: Any, widget: Widget) -> None:"),
        ],
    }


PYTEST_PACK_TYPECHECK = [
    "tests/conftest.py", "tests/test_parametrize.py", "tests/test_mocking.py", "tests/db/conftest.py",
    "tests/db/test_async_patterns.py", "docs_fragments/assertions.py",
]
UNITS.append(Unit(
    name="pack-pytest",
    own=[PT],
    files=pytest_pack_files(),
    typecheck=PYTEST_PACK_TYPECHECK,
    imports=["docs_fragments.assertions"],
    smoke=smoke("smoke_pytest_assertions.py"),
    pytest="run",
    # the doc's own setting (asyncio_mode = "auto"); the database tests run in pack-pytest-live
    pytest_args=["-o", "asyncio_mode=auto", "--ignore=tests/db/test_db_fixtures_live.py",
                 "-k", "not test_transaction_rollback"],
))

UNITS.append(Unit(
    name="pack-pytest-live",
    own=[PT],
    files=pytest_pack_files(),
    typecheck=[],  # pack-pytest type-checks the same files
    imports=[],
    pytest="collect",
    live="run",
    pytest_args=["-o", "asyncio_mode=auto", "tests/db"],
))

# ── languages/python.md: the general blocks (errors, pytest, logging, typing, performance, async, shutdown) ──
PYB = "from harness_stubs.py_basics import "
UNITS.append(Unit(
    name="pack-python-basics",
    own=[PY],
    files={
        "harness_stubs/py_basics.py": [stub("py_basics.py")],
        "docs_fragments/domain_errors.py": [
            T(PYB + "DBConnectionError, RepositoryError, db  # harness: the app's names"),
            B(PY, 0, "# Define domain errors", wrap="async def get_user(user_id: str) -> object:"),
        ],
        "tests/test_email.py": [
            T("import pytest\n\n" + PYB + "validate_email  # harness: the function under test"),
            B(PY, 1, '@pytest.mark.parametrize("input,expected", ['),
        ],
        "docs_fragments/logging_example.py": [T(PYB + "user  # harness: the user just created"), B(PY, 2, "import structlog")],
        "docs_fragments/types.py": [
            T(PYB + "User, UserNotFoundError, db  # harness: the app's names"),
            B(PY, 3, "from typing import NotRequired, TypedDict, Protocol, Literal, TypeVar, overload, Generic"),
        ],
        "docs_fragments/perf.py": [T(PYB + "Result, resize_image  # harness: the app's names"), B(PY, 4, "import asyncio")],
        "docs_fragments/task_groups.py": [
            T(PYB + "UserProfile, fetch_orders, fetch_preferences, fetch_profile  # harness: the app's names"),
            B(PY, 21, "import asyncio"),
        ],
        "docs_fragments/semaphores.py": [B(PY, 22, "import asyncio")],
        "docs_fragments/shutdown.py": [
            T(PYB + "create_db_pool, create_redis, log  # harness: the app's resources"),
            B(PY, 23, "from collections.abc import AsyncGenerator"),
        ],
    },
    smoke=smoke("smoke_python_basics.py"),
    pytest="run",
))

# ── languages/python.md "ML-Specific Patterns": numpy + torch on CPU; the usage lines run at import ──
_JSONL = "\n".join(
    '{"id": %d, "status": "%s"}' % (i, "active" if i % 2 == 0 else "inactive") for i in range(3000))
UNITS.append(Unit(
    name="pack-python-ml",
    own=[PY],
    files={
        "harness_stubs/ml_app.py": [stub("ml_app.py")],
        "data.jsonl": [T(_JSONL)],  # the file the doc's pipeline reads
        "ml/pipeline.py": [
            T("from harness_stubs.ml_app import data, extract_features, model, process  # harness: app names"),
            B(PY, 5, "import json"),
        ],
    },
    smoke=smoke("smoke_python_ml.py"),
))

# ── languages/python.md, the FastAPI blocks as one app: types, error hierarchy, handlers, tenant dependency,
# SQLAlchemy tenant filter, tenant middleware, DI (TestClient), plus the filter on SQLite ─────────────
PYF = "from harness_stubs.py_fastapi import "
UNITS.append(Unit(
    name="pack-python-fastapi",
    own=[PY],
    files={
        "harness_stubs/py_basics.py": [stub("py_basics.py")],
        "harness_stubs/py_fastapi.py": [stub("py_fastapi.py")],
        "harness_stubs/py_fastapi_main.py": [stub("py_fastapi_main.py")],
        "app/types.py": [
            T("from harness_stubs.py_basics import User, UserNotFoundError, db  # harness: the app's names"),
            B(PY, 3, "from typing import NotRequired, TypedDict, Protocol, Literal, TypeVar, overload, Generic"),
        ],
        "app/errors.py": [B(PY, 9, "from typing import TypedDict")],
        "app/handlers.py": [
            T("from app.errors import (  # harness: the hierarchy above, in its own module\n"
              "    AppError, FieldError, ForbiddenError, InternalError, MalformedRequestError, NotFoundError,\n"
              "    RateLimitError, UnauthenticatedError, ValidationError,\n)"),
            B(PY, 10, "from collections.abc import Mapping"),
        ],
        "app/tenancy.py": [
            T("from app.errors import ForbiddenError\nfrom app.handlers import get_request_id\n"
              "from app.types import PaginatedResponse\n"
              + PYF + "OrderResponse, OrderService, get_order_service, get_verified_claims\n"
              + PYF + "orders_router as router"),
            B(PY, 6, "from fastapi import Depends, Header, Query, Request"),
        ],
        "app/db_tenant.py": [B(PY, 7, "from contextvars import ContextVar")],
        "app/tenant_middleware.py": [
            T("from fastapi import Request\n\nfrom app.db_tenant import current_tenant\n"
              "from app.errors import ForbiddenError, UnauthenticatedError\nfrom app.handlers import error_response\n"
              "from app.tenancy import TokenClaims, resolve_tenant"),
            B(PY, 8, "from starlette.middleware.base import BaseHTTPMiddleware"),
        ],
        "app/users.py": [
            T("from app.handlers import get_request_id\nfrom app.tenancy import get_current_tenant\n"
              "from app.types import ApiResponse\n"
              + PYF + "(\n    CacheService, CreateUserRequest, EventPublisher, UserRepository, UserResponse, UserService,\n"
              "    async_session_factory, get_cache, get_event_publisher,\n)\n"
              + PYF + "users_router as router"),
            B(PY, 14, "from collections.abc import AsyncGenerator"),
        ],
        "tests/test_python_fastapi.py": [stub("test_python_fastapi.py")],
        "tests/test_python_field_codes.py": [stub("test_python_field_codes.py")],
    },
    imports=["app.types", "app.errors", "app.handlers", "app.tenancy", "app.db_tenant", "app.tenant_middleware",
             "app.users"],
    pytest="run",
))
