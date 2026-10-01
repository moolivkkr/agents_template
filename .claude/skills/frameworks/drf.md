# Django REST Framework patterns for Python REST APIs.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): type-checked, imported, and run as one Django project on SQLite: the doc's APITestCase suite under Django's test runner, plus requests through every block (envelope bodies, cursor pages and the `limit` bounds, optimistic-locking update, permissions, JWT with iss/aud, the error handler's 400/401/404/405/409/500). Django 6.1.1, Django REST framework 3.18.1, django-filter 26.1, djangorestframework-simplejwt 5.5.1, factory_boy 3.3.3.

## Project Structure
```
myapp/
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── local.py         # Local dev overrides
│   │   └── production.py    # Production settings
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── apps/
│   └── widgets/
│       ├── __init__.py
│       ├── models.py         # Django ORM models
│       ├── serializers.py    # DRF serializers (request/response schemas)
│       ├── views.py          # ViewSets or APIViews
│       ├── urls.py           # Router registration
│       ├── permissions.py    # Custom permission classes
│       ├── filters.py        # django-filter FilterSets
│       ├── services.py       # Business logic (NOT in views)
│       ├── signals.py        # Django signals (use sparingly)
│       └── tests/
│           ├── test_views.py
│           ├── test_serializers.py
│           └── test_services.py
```
- One Django app per bounded context (widgets, users, billing)
- Views are thin: validate request, call service, return response
- Business logic lives in `services.py` — never in views or serializers

## Serializers
```python
from rest_framework import serializers
from .models import Widget

class WidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Widget
        fields = ["id", "name", "description", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class WidgetWriteSerializer(serializers.Serializer):
    """Base of the write serializers: validates the input, answers with the read shape."""

    def to_representation(self, instance):
        return WidgetSerializer(instance, context=self.context).data

class CreateWidgetSerializer(WidgetWriteSerializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=2000, required=False, default="")
    status = serializers.ChoiceField(choices=["active", "draft"], default="active")

    def validate_name(self, value):
        """Custom per-field validation."""
        if Widget.objects.filter(
            tenant_id=self.context["request"].user.tenant_id,
            name__iexact=value,
            deleted_at__isnull=True,
        ).exists():
            # code= becomes details[].code; the client sees FIELD_MESSAGES["already_exists"] (exception handler)
            raise serializers.ValidationError("A widget with this name already exists.", code="already_exists")
        return value.strip()

    def validate(self, attrs):
        """Cross-field validation."""
        if attrs.get("status") == "active" and not attrs.get("name"):
            raise serializers.ValidationError({"name": "Active widgets must have a name."}, code="required")
        return attrs

class UpdateWidgetSerializer(WidgetWriteSerializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=2000, required=False)
    version = serializers.IntegerField(required=True)

    def validate(self, attrs):
        # PATCH validates with partial=True, which skips `required`: the lock version is still needed
        if "version" not in attrs:
            raise serializers.ValidationError({"version": "This field is required."}, code="required")
        return attrs
```
- Use `ModelSerializer` for read serializers — auto-generates fields from model
- Use plain `Serializer` for write operations — explicit control over input validation; their
  `to_representation` returns the read shape, so a 201/200 body is the resource, not the echoed input
- `validate_<field>` for per-field validation, `validate()` for cross-field rules
- Raise `ValidationError(..., code="<lower_snake>")` with a code from the envelope's closed set
  (`api/response-envelope.md`) — it reaches `details[].code`; DRF's own codes (`blank`, `max_length`, …) are
  mapped onto the set, and the text you write is replaced by the catalog message for that code (Custom
  Exception Handler below)
- Pass `context={"request": request}` for tenant-scoped uniqueness checks

## ViewSets and Routers
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class WidgetViewSet(viewsets.ModelViewSet):
    # Bodies are the envelope: EnvelopeJSONRenderer wraps success data, EnvelopeCursorPagination
    # shapes lists, custom_exception_handler shapes errors (api/response-envelope.md)
    serializer_class = WidgetSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    filterset_class = WidgetFilterSet
    pagination_class = EnvelopeCursorPagination

    def get_queryset(self):
        """Tenant-scoped queryset — every query filters by tenant."""
        return Widget.objects.filter(
            tenant_id=self.request.user.tenant_id,
            deleted_at__isnull=True,
        ).select_related("category").order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return CreateWidgetSerializer
        if self.action in ("update", "partial_update"):
            return UpdateWidgetSerializer
        return WidgetSerializer

    def perform_create(self, serializer):
        """Delegate to service layer — never put business logic here."""
        widget = WidgetService.create(
            tenant_id=self.request.user.tenant_id,
            user_id=self.request.user.id,
            **serializer.validated_data,
        )
        serializer.instance = widget

    def perform_update(self, serializer):
        """Optimistic locking in the service: a stale `version` raises ConflictError (409)."""
        serializer.instance = WidgetService.update(
            serializer.instance, self.request.user.id, **serializer.validated_data,
        )

    def perform_destroy(self, instance):
        """Soft delete — set deleted_at instead of removing."""
        WidgetService.soft_delete(instance, self.request.user.id)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """Custom action: POST /widgets/{id}/archive/"""
        widget = self.get_object()
        widget = WidgetService.archive(widget, request.user.id)
        return Response(WidgetSerializer(widget).data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Custom collection action: GET /widgets/stats/"""
        stats = WidgetService.get_stats(request.user.tenant_id)
        return Response(stats)

# urls.py
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"widgets", WidgetViewSet, basename="widget")
urlpatterns = router.urls
```
- `ModelViewSet` provides list, create, retrieve, update, partial_update, destroy
- Override `get_queryset()` to enforce tenant isolation — never return unscoped querysets
- Override `get_serializer_class()` for different read/write serializers
- Writes go through the service: `perform_create` / `perform_update` / `perform_destroy` (a plain
  `Serializer` has no `create()`/`update()` of its own)
- `@action` decorator for custom endpoints beyond CRUD
- `DefaultRouter` auto-generates URL patterns from ViewSets

## Permissions
```python
from rest_framework.permissions import BasePermission

class IsTenantMember(BasePermission):
    """Ensure the user belongs to the tenant owning the resource."""

    def has_permission(self, request, view):
        return hasattr(request.user, "tenant_id") and request.user.tenant_id is not None

    def has_object_permission(self, request, view, obj):
        return obj.tenant_id == request.user.tenant_id

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff or "admin" in getattr(request.user, "roles", [])

class HasPermission(BasePermission):
    """Check for a specific permission string:
    permission_classes = [IsAuthenticated, HasPermission("widgets.archive")]"""

    def __init__(self, required_permission):
        self.required_permission = required_permission

    def __call__(self):
        # DRF instantiates every permission_classes entry (`permission()`): an instance returns itself
        return self

    def has_permission(self, request, view):
        user_permissions = getattr(request.user, "permissions", [])
        return self.required_permission in user_permissions
```
- `has_permission()` runs before the view — use for collection-level checks
- `has_object_permission()` runs after `get_object()` — use for row-level checks
- Stack permissions: `permission_classes = [IsAuthenticated, IsTenantMember, IsAdminOrReadOnly]`
- All permissions must pass (AND logic) — for OR logic, create a composite permission

## Filtering and Pagination
```python
from urllib.parse import parse_qs, urlparse

import django_filters
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

# Filtering with django-filter
class WidgetFilterSet(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=[("active", "Active"), ("draft", "Draft")])
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Widget
        fields = ["status"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)

# apps/core/pagination.py — the only paginator: cursor-based, ?cursor=<opaque>&limit=<n>,
# answering the list envelope {"data": [...], "meta": {"request_id", "pagination": {...}}}
class EnvelopeCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "limit"   # the envelope's name for page size
    max_page_size = 100
    ordering = "-created_at"           # an unchanging, (nearly) unique field — DRF's cursor requirement
    cursor_query_param = "cursor"

    def get_page_size(self, request):
        # DRF's own get_page_size clamps to max_page_size and ignores junk: the envelope makes a limit
        # outside 1..max a 400 VALIDATION_FAILED instead (a client asking for 500 must know it got 100)
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return self.page_size
        try:
            limit = int(raw)
        except ValueError:
            raise ValidationError({"limit": "Must be a whole number."}, code="invalid_type") from None
        if not 1 <= limit <= self.max_page_size:
            raise ValidationError({"limit": f"Must be 1 to {self.max_page_size}."}, code="out_of_range")
        return limit

    def get_paginated_response(self, data):
        response = Response({
            "data": data,  # always a list — [] when empty
            "meta": {
                "request_id": getattr(self.request, "request_id", ""),
                "pagination": {
                    "next_cursor": self._cursor_value(self.get_next_link()),
                    "has_more": self.has_next,
                    "limit": self.page_size,  # effective size after max_page_size
                },
            },
        })
        response.enveloped = True  # EnvelopeJSONRenderer passes it through unwrapped
        return response

    def _cursor_value(self, link):
        # DRF's next link is a full URL; the envelope carries only the opaque cursor value from it
        if link is None:
            return None
        return parse_qs(urlparse(link).query).get(self.cursor_query_param, [None])[0]
```
- Cursor pagination only — for public APIs and admin UIs alike (no page-number or limit/offset paginators;
  `meta.pagination.total_count` is optional, only when cheap and the UI shows it)
- `?limit=` is the page-size parameter; `next_cursor` is `null` when `has_more` is false
- Always set `max_page_size` — never return unbounded results; a `limit` outside `1..max_page_size` is a
  400 `VALIDATION_FAILED` with a `details[]` entry for `limit`, never silently clamped
- No `OrderingFilter`: a client-chosen ordering would replace the cursor's stable sort key
- Use `django-filter` for declarative filtering — never parse query params manually

## Authentication
```python
# settings.py
import os
from datetime import timedelta

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.EnvelopeCursorPagination",
    "DEFAULT_RENDERER_CLASSES": ["apps.core.renderers.EnvelopeJSONRenderer"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",  # no OrderingFilter: the cursor fixes the order
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

# No defaults: a missing key, issuer or audience stops the process at start-up. With ISSUER and AUDIENCE
# set, simplejwt writes iss/aud into every token and rejects a token without them or minted elsewhere.
SIMPLE_JWT = {
    "SIGNING_KEY": os.environ["JWT_SIGNING_KEY"],
    "ISSUER": os.environ["JWT_ISSUER"],
    "AUDIENCE": os.environ["JWT_AUDIENCE"],
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "TOKEN_OBTAIN_SERIALIZER": "apps.users.serializers.CustomTokenObtainPairSerializer",
}
```

```python
# apps/users/serializers.py — custom JWT claims (never import DRF serializers from settings.py)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id)
        token["roles"] = list(user.groups.values_list("name", flat=True))
        return token
```
- Use `djangorestframework-simplejwt` for JWT — never roll your own JWT
- Add custom claims (tenant_id, roles) to the token payload
- Signing key, issuer and audience come from the environment with no default (`SIMPLE_JWT`); iss and aud
  are then required on every token
- Set authentication and permission classes globally in `REST_FRAMEWORK` settings

## Custom Exception Handler
DRF's default error bodies (a `detail` string, or a `{field: [messages]}` dict for validation) are not the
envelope, and anything that isn't an `APIException` falls through to Django's HTML 500 page. This handler
replaces all of them with `{"error": {code, message, details?, request_id, retryable}}`. `exc.detail` text is
never copied into the body.
```python
# apps/core/exceptions.py
import logging

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

log = logging.getLogger(__name__)

class AppError(exceptions.APIException):
    """Domain errors raised from services.py. `message` is user-safe catalog text."""
    status_code = 500
    code = "INTERNAL"
    message = "Something went wrong."
    retryable = False

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(detail=self.message, code=self.code)

class ConflictError(AppError):        # 409: duplicate, version mismatch, state conflict
    status_code, code, message = 409, "CONFLICT", "This was changed by someone else. Reload and try again."

class BusinessRuleError(AppError):    # 422: valid shape, rejected by a domain rule
    status_code, code = 422, "BUSINESS_RULE_VIOLATION"

class UnavailableError(AppError):     # 503: raise UnavailableError() from exc — the cause is logged, not sent
    status_code, code, message, retryable = 503, "UNAVAILABLE", "The service is temporarily unavailable.", True

# Other exceptions: code + user-safe message by the status DRF assigned. This also covers Django's Http404
# and PermissionDenied, which DRF's exception_handler converts internally.
_BY_STATUS = {
    400: ("MALFORMED_REQUEST", "The request could not be read."),   # ParseError: unreadable JSON
    # 401 needs an authenticator with a WWW-Authenticate header first (JWTAuthentication has one),
    # or DRF downgrades it to 403
    401: ("UNAUTHENTICATED", "Sign in to continue."),
    403: ("FORBIDDEN", "You don't have permission to do this."),
    404: ("NOT_FOUND", "Not found."),                                # also another tenant's object
    415: ("MALFORMED_REQUEST", "The request could not be read."),   # sent as 400
    429: ("RATE_LIMITED", "Too many requests. Try again shortly."),  # DRF sets Retry-After
}

# details[].code comes from the envelope's closed set (api/response-envelope.md). DRF's ErrorDetail.code is
# its own vocabulary (blank, max_length, min_value, invalid_choice, unique, …): mapped onto the set here; a
# code already in the set (raised with code=...) passes through. Each wire code has one catalog message;
# DRF's own text (which can echo the input) is not sent.
FIELD_CODES = {
    "required": "required", "blank": "required", "null": "required",
    "max_length": "too_long", "min_length": "too_short",
    "min_value": "out_of_range", "max_value": "out_of_range",
    "invalid_choice": "invalid_value", "unique": "already_exists",
}
FIELD_MESSAGES = {
    "required": "This field is required.",
    "invalid_type": "This value has the wrong type.",
    "invalid_format": "This value has the wrong format.",
    "invalid_value": "This value is invalid.",
    "out_of_range": "This value is out of range.",
    "too_short": "This value is too short.",
    "too_long": "This value is too long.",
    "unknown_field": "This field is not accepted.",
    "invalid_cursor": "This cursor is not valid.",
    "already_exists": "This value is already in use.",
}

def _field_errors(detail, field=""):
    """Flatten ValidationError.detail (dicts, lists, nested serializers) into details[]."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            yield from _field_errors(value, f"{field}.{key}" if field else str(key))
    elif isinstance(detail, list):
        for i, item in enumerate(detail):
            nested = isinstance(item, (dict, list))
            yield from _field_errors(item, (f"{field}.{i}" if field else str(i)) if nested else field)
    else:
        native = getattr(detail, "code", "") or ""
        code = native if native in FIELD_MESSAGES else FIELD_CODES.get(native, "invalid_value")
        yield {"field": field, "code": code, "message": FIELD_MESSAGES[code]}

def _body(code, message, request_id, details=None, retryable=False):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    error["request_id"] = request_id
    error["retryable"] = retryable
    return {"error": error}

def custom_exception_handler(exc, context):
    # request.request_id: set by the request-id middleware (first in MIDDLEWARE), which also sets X-Request-Id
    request_id = getattr(context.get("request"), "request_id", "")
    response = exception_handler(exc, context)  # converts Http404/PermissionDenied, sets auth/Retry-After headers

    if response is None:  # not an APIException: unexpected → 500 INTERNAL, cause logged under request_id
        log.error("unhandled_error", exc_info=exc, extra={"request_id": request_id})
        return Response(_body("INTERNAL", "Something went wrong.", request_id), status=500)

    if isinstance(exc, exceptions.ValidationError):
        response.status_code = 400  # serializer/field validation → 400 VALIDATION_FAILED
        response.data = _body("VALIDATION_FAILED", "Some fields are invalid.", request_id,
                              details=list(_field_errors(exc.detail)))
        return response

    if isinstance(exc, AppError):
        code, message, retryable = exc.code, exc.message, exc.retryable
    elif response.status_code >= 500:
        code, message, retryable = "INTERNAL", "Something went wrong.", False
    else:  # unlisted 4xx (405, 406, …) keep their status and read as MALFORMED_REQUEST
        code, message = _BY_STATUS.get(response.status_code, _BY_STATUS[400])
        retryable = response.status_code == 429
    if response.status_code == 415:
        response.status_code = 400
    if response.status_code >= 500:
        log.error("request_failed", exc_info=exc, extra={"request_id": request_id, "code": code})
    response.data = _body(code, message, request_id, retryable=retryable)
    return response
```

## Success Envelope (Renderer)
```python
# apps/core/renderers.py — wraps every success body as {"data": ..., "meta": {"request_id": ...}}.
# Error bodies (custom_exception_handler) and list bodies (EnvelopeCursorPagination) arrive already shaped.
from rest_framework.renderers import JSONRenderer

class EnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        response = context.get("response")
        if response is not None and response.status_code != 204 and not (
            response.exception or getattr(response, "enveloped", False)
        ):
            request_id = getattr(context.get("request"), "request_id", "")
            data = {"data": data, "meta": {"request_id": request_id}}
        return super().render(data, accepted_media_type, renderer_context)
```
- One renderer for the whole API (`DEFAULT_RENDERER_CLASSES`) — views return plain serializer data and never
  build the envelope by hand
- 204 responses stay empty; error responses (`response.exception`) and paginated lists pass through

## Testing (APITestCase, APIClient)
```python
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

class WidgetViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(tenant_id=uuid4())
        self.client.force_authenticate(user=self.user)

    def test_create_widget(self):
        data = {"name": "New Widget", "description": "Test"}
        response = self.client.post("/api/v1/widgets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()  # the rendered envelope (response.data is the pre-render payload)
        self.assertEqual(body["data"]["name"], "New Widget")
        self.assertIn("request_id", body["meta"])
        self.assertTrue(Widget.objects.filter(name="New Widget").exists())

    def test_create_widget_missing_name_returns_400_validation_failed(self):
        response = self.client.post("/api/v1/widgets/", {"description": "no name"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.json()["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"][0], {"field": "name", "code": "required",
                                               "message": "This field is required."})
        self.assertNotIn("data", response.json())

    def test_list_widgets_tenant_isolation(self):
        WidgetFactory(tenant_id=self.user.tenant_id)
        WidgetFactory(tenant_id=uuid4())  # different tenant

        response = self.client.get("/api/v1/widgets/")
        body = response.json()
        self.assertEqual(len(body["data"]), 1)
        self.assertFalse(body["meta"]["pagination"]["has_more"])
        self.assertIsNone(body["meta"]["pagination"]["next_cursor"])

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/widgets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHENTICATED")

    def test_wrong_tenant_returns_404(self):
        widget = WidgetFactory(tenant_id=uuid4())
        response = self.client.get(f"/api/v1/widgets/{widget.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")
```
- `force_authenticate()` bypasses JWT parsing in tests — test business logic, not auth library
- Assert on `response.json()` (the rendered envelope), not `response.data`
- Always test tenant isolation: user A cannot see user B's resources
- Use factories (factory_boy) for test data — never create fixtures manually

## Signals vs Explicit Service Calls
```python
# PREFER: Explicit service calls — predictable, testable, traceable
class WidgetService:
    @staticmethod
    def create(tenant_id, user_id, **data):
        widget = Widget.objects.create(tenant_id=tenant_id, created_by=user_id, **data)
        AuditLog.objects.create(action="widget.created", entity_id=widget.id, actor_id=user_id)
        NotificationService.send(tenant_id, "widget_created", widget)
        return widget

# AVOID: Django signals — implicit, hard to debug, hidden side effects
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Widget)
def widget_post_save(sender, instance, created, **kwargs):
    if created:  # hidden, runs in same transaction, hard to test
        AuditLog.objects.create(action="widget.created", entity_id=instance.id, actor_id=instance.created_by)
```
- Prefer explicit service calls over signals for business logic
- Signals are acceptable for: cache invalidation, search index updates, denormalization
- Never put critical business logic in signals — they are implicit and hard to trace

## Rules
- `get_queryset()` MUST filter by `tenant_id` — never return unscoped querysets
- Business logic lives in `services.py` — views and serializers are thin adapters
- Use `ModelSerializer` for reads, plain `Serializer` for writes
- `EnvelopeCursorPagination` (`?cursor=` + `?limit=`) for every list — no page-number or limit/offset paginators;
  a `limit` outside `1..max_page_size` is a 400, never clamped
- Always set `max_page_size` — never return unbounded results
- Every body is the envelope (`api/response-envelope.md`): `EnvelopeJSONRenderer` for success,
  `custom_exception_handler` for errors — `{"error": {code, message, details?, request_id, retryable}}`,
  replacing DRF's default `detail` bodies; exception text never reaches the client
- Soft delete: override `perform_destroy`, never actually delete rows
- Use `force_authenticate()` in tests — never test JWT library internals
- Prefer explicit service calls over Django signals for business logic
- Use `django-filter` for query parameter filtering — never parse params manually
