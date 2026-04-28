# Django patterns for production-ready Python web applications.

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
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email"])]
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
        return super().get_queryset().filter(is_active=True)
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
