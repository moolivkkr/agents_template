# Django patterns for production-ready Python web applications.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): type-checked, imported, `manage.py check` clean, and run on SQLite through DRF's APIClient (the tenant-scoped ViewSet, the serializer, the select_related/prefetch_related query counts). Django 6.1.1, Django REST framework 3.18.1.

## Project Layout
```
myproject/
  settings/
    base.py        # shared settings
    development.py # local overrides
    production.py  # prod overrides
  urls.py
  wsgi.py
myapp/
  models.py
  views.py         # or viewsets.py for DRF
  serializers.py
  urls.py
  admin.py
  apps.py
  migrations/
manage.py
```

## Models
```python
class User(models.Model):
    tenant_id = models.UUIDField()               # set from the verified token, never from input
    email = models.EmailField(unique=True)       # unique=True already creates an index
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant_id", "-created_at"])]  # the tenant's list, newest first
```
- Always define `class Meta` with explicit `db_table`
- `auto_now_add` for created; `auto_now` for updated
- Never edit deployed migrations — create new ones

## DRF Serializers
```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "created_at"]
        read_only_fields = ["id", "created_at"]
```

## ViewSets
```python
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Every query is scoped to the caller's tenant (from the authenticated user, never the request):
        # another tenant's user is a 404
        return super().get_queryset().filter(tenant_id=self.request.user.tenant_id, is_active=True)

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.user.tenant_id)
```

## Query Optimization
```python
# Always use select_related (FK) and prefetch_related (M2M/reverse FK)
users = User.objects.select_related("profile").prefetch_related("groups").filter(is_active=True)

# Use values() for read-only aggregations
User.objects.values("department").annotate(count=Count("id"))
```
- Avoid N+1 with `select_related` / `prefetch_related`
- Use `only()` for large models when you need a few fields
- Never load entire querysets into memory — iterate or paginate

## Rules
- `SECRET_KEY` and `DATABASE_URL` from environment — never in code
- `DEBUG=False` in production; whitelist `ALLOWED_HOSTS`
- Signals: use sparingly — prefer explicit service calls
- `python manage.py check --deploy` before production deploy
