# frameworks/django.md: system checks, then the ViewSet through DRF's APIClient on SQLite (tenant scoping,
# create, 404 for another tenant), the serializer, and the query-optimization fragment's query count.
from types import SimpleNamespace
from uuid import uuid4

import django

django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext, setup_test_environment  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

setup_test_environment()
call_command("check", fail_level="WARNING")
call_command("migrate", run_syncdb=True, verbosity=0)

import directory.queries as queries  # noqa: E402 — the fragment builds its querysets at import
from directory.models import Profile as DirProfile, User as DirUser  # noqa: E402
from myapp.models import Profile, User  # noqa: E402
from myapp.serializers import UserSerializer  # noqa: E402

tenant_a, tenant_b = uuid4(), uuid4()
a1 = User.objects.create(tenant_id=tenant_a, email="a1@example.com")
User.objects.create(tenant_id=tenant_a, email="a-inactive@example.com", is_active=False)
b1 = User.objects.create(tenant_id=tenant_b, email="b1@example.com")
Profile.objects.create(user=a1)

client = APIClient()
client.force_authenticate(user=SimpleNamespace(is_authenticated=True, tenant_id=tenant_a, pk=1))
r = client.get("/users/")
assert r.status_code == 200, r.content
assert [u["email"] for u in r.json()["results"]] == ["a1@example.com"], r.json()
assert client.get(f"/users/{b1.pk}/").status_code == 404  # another tenant's user
assert client.get(f"/users/{a1.pk}/").json()["email"] == "a1@example.com"
r = client.post("/users/", {"email": "new@example.com", "tenant_id": str(tenant_b)}, format="json")
assert r.status_code == 201, r.content
assert User.objects.get(email="new@example.com").tenant_id == tenant_a  # from the user, not the body
assert set(UserSerializer(a1).data) == {"id", "email", "created_at"}

# select_related + prefetch_related: two queries for the whole list, whatever its length
from django.contrib.auth.models import Group  # noqa: E402

g = Group.objects.create(name="staff")
for i in range(5):
    u = DirUser.objects.create(email=f"d{i}@example.com", department="eng" if i % 2 else "ops")
    DirProfile.objects.create(user=u, title=f"t{i}")
    u.groups.add(g)
with CaptureQueriesContext(connection) as ctx:
    rows = [(u.profile.title, [x.name for x in u.groups.all()]) for u in queries.users]
assert len(rows) == 5 and len(ctx.captured_queries) == 2, (len(rows), ctx.captured_queries)
# (the fragment's values("department").annotate(...) line resolved its fields when the module imported)
