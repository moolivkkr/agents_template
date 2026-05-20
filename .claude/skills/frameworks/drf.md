# Django REST Framework patterns for Python REST APIs.

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

class CreateWidgetSerializer(serializers.Serializer):
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
            raise serializers.ValidationError("A widget with this name already exists.")
        return value.strip()

    def validate(self, data):
        """Cross-field validation."""
        if data.get("status") == "active" and not data.get("name"):
            raise serializers.ValidationError("Active widgets must have a name.")
        return data

class UpdateWidgetSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=2000, required=False)
    version = serializers.IntegerField(required=True)
```
- Use `ModelSerializer` for read serializers — auto-generates fields from model
- Use plain `Serializer` for write operations — explicit control over input validation
- `validate_<field>` for per-field validation, `validate()` for cross-field rules
- Pass `context={"request": request}` for tenant-scoped uniqueness checks

## ViewSets and Routers
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class WidgetViewSet(viewsets.ModelViewSet):
    serializer_class = WidgetSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    filterset_class = WidgetFilterSet
    pagination_class = CursorPagination

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
    """Check for specific permission strings."""

    def __init__(self, required_permission):
        self.required_permission = required_permission

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
import django_filters
from rest_framework.pagination import CursorPagination, PageNumberPagination

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

# Cursor pagination (default for APIs)
class WidgetCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    ordering = "-created_at"
    cursor_query_param = "cursor"

# Offset pagination (for admin UIs)
class WidgetPagePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
```
- Use `CursorPagination` for public APIs — stable, performant, no counting
- Use `PageNumberPagination` for admin dashboards — supports "jump to page N"
- Always set `max_page_size` — never return unbounded results
- Use `django-filter` for declarative filtering — never parse query params manually

## Authentication
```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.WidgetCursorPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

# Custom JWT claims
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
- Set authentication and permission classes globally in `REST_FRAMEWORK` settings

## Custom Exception Handler
```python
from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_body = {
            "error": {
                "code": _get_error_code(exc),
                "message": _get_error_message(exc, response),
            }
        }
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            error_body["error"]["details"] = exc.detail
        response.data = error_body

    return response

def _get_error_code(exc):
    from rest_framework.exceptions import (
        NotFound, PermissionDenied, AuthenticationFailed,
        ValidationError, Throttled,
    )
    mapping = {
        NotFound: "NOT_FOUND",
        PermissionDenied: "FORBIDDEN",
        AuthenticationFailed: "UNAUTHORIZED",
        ValidationError: "VALIDATION_ERROR",
        Throttled: "RATE_LIMITED",
    }
    return mapping.get(type(exc), "INTERNAL_ERROR")

def _get_error_message(exc, response):
    if response.status_code >= 500:
        return "an unexpected error occurred"
    return str(exc.detail) if hasattr(exc, "detail") else str(exc)
```

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
        self.assertEqual(response.data["data"]["name"], "New Widget")
        self.assertTrue(Widget.objects.filter(name="New Widget").exists())

    def test_list_widgets_tenant_isolation(self):
        WidgetFactory(tenant_id=self.user.tenant_id)
        WidgetFactory(tenant_id=uuid4())  # different tenant

        response = self.client.get("/api/v1/widgets/")
        self.assertEqual(len(response.data["results"]), 1)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/widgets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_tenant_returns_404(self):
        widget = WidgetFactory(tenant_id=uuid4())
        response = self.client.get(f"/api/v1/widgets/{widget.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
```
- `force_authenticate()` bypasses JWT parsing in tests — test business logic, not auth library
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
    if created:
        AuditLog.objects.create(...)  # hidden, runs in same transaction, hard to test
```
- Prefer explicit service calls over signals for business logic
- Signals are acceptable for: cache invalidation, search index updates, denormalization
- Never put critical business logic in signals — they are implicit and hard to trace

## Rules
- `get_queryset()` MUST filter by `tenant_id` — never return unscoped querysets
- Business logic lives in `services.py` — views and serializers are thin adapters
- Use `ModelSerializer` for reads, plain `Serializer` for writes
- `CursorPagination` for public APIs, `PageNumberPagination` for admin UIs
- Always set `max_page_size` — never return unbounded results
- Custom exception handler wraps all errors in `{"error": {"code": ..., "message": ...}}`
- Soft delete: override `perform_destroy`, never actually delete rows
- Use `force_authenticate()` in tests — never test JWT library internals
- Prefer explicit service calls over Django signals for business logic
- Use `django-filter` for query parameter filtering — never parse params manually
