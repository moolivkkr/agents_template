# languages/python.md's Django blocks on SQLite: the tenant middleware with a real simplejwt token (and
# the session-user branch), the fail-closed tenant manager, the DRF serializer, the audit signals.
from types import SimpleNamespace
from uuid import uuid4

import django

django.setup()

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from rest_framework_simplejwt.tokens import AccessToken  # noqa: E402

call_command("check", fail_level="WARNING")
call_command("migrate", run_syncdb=True, verbosity=0)

import myapp.signals  # noqa: E402,F401 — registers the doc's receivers
from accounts.models import User  # noqa: E402
from myapp.middleware import TenantMiddleware, _thread_local, get_current_tenant  # noqa: E402
from myapp.models import AuditLog, Order  # noqa: E402
from myapp.serializers import OrderSerializer  # noqa: E402

tenant_a, tenant_b = uuid4(), uuid4()
alice = User.objects.create_user("alice", password="pw", tenant_id=tenant_a)

seen: dict[str, object] = {}


def view(request):
    seen["thread_local"] = get_current_tenant()
    seen["request"] = request.tenant_id
    return HttpResponse("ok")


mw = TenantMiddleware(view)
rf = RequestFactory()

# a verified JWT carrying the tenant
token = AccessToken.for_user(alice)
token["tenant_id"] = str(tenant_a)
req = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
req.user = AnonymousUser()
mw(req)
assert seen == {"thread_local": str(tenant_a), "request": str(tenant_a)}, seen
assert get_current_tenant() is None  # reset after the request

# a forged token (wrong signature) and a bare X-Tenant-ID header grant nothing
forged = str(token)[:-2] + ("AA" if not str(token).endswith("AA") else "BB")
for headers in ({"HTTP_AUTHORIZATION": f"Bearer {forged}"}, {"HTTP_X_TENANT_ID": str(tenant_b)}):
    req = rf.get("/", **headers)
    req.user = AnonymousUser()
    mw(req)
    assert seen == {"thread_local": None, "request": None}, (headers, seen)

# a session-authenticated user: the tenant comes from the user record
req = rf.get("/")
req.user = alice
mw(req)
assert seen["request"] == str(tenant_a), seen

# the manager fails closed without a tenant, and filters by the current one
Order.all_objects.create(tenant_id=tenant_a, status="open", total=100)
Order.all_objects.create(tenant_id=tenant_b, status="open", total=200)
assert list(Order.objects.all()) == []
_thread_local.tenant_id = str(tenant_a)
try:
    assert [o.total for o in Order.objects.all()] == [100]
finally:
    _thread_local.tenant_id = None

# the serializer takes the tenant from the request, never the body; a negative total is out_of_range
s = OrderSerializer(data={"status": "open", "total": 50, "tenant_id": str(tenant_b)},
                    context={"request": SimpleNamespace(tenant_id=str(tenant_a))})
assert s.is_valid(), s.errors
order = s.save()
assert str(order.tenant_id) == str(tenant_a)
bad = OrderSerializer(data={"status": "open", "total": -5}, context={"request": SimpleNamespace(tenant_id="x")})
assert not bad.is_valid() and bad.errors["total"][0].code == "out_of_range", bad.errors

# audit signals: create and update are logged with the tracked changes; a hard delete is refused
order.status = "paid"
order.save()
actions = list(AuditLog.objects.filter(entity_id=order.id).values_list("action", "changes"))
assert [a for a, _ in actions] == ["created", "updated"], actions
assert actions[1][1] == {"status": "open"}, actions  # the previous value of the changed field
try:
    order.delete()
except ValueError:
    pass
else:
    raise AssertionError("a hard delete went through")
