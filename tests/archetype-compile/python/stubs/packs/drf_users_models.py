"""harness: the custom user frameworks/drf.md assumes (request.user.tenant_id, roles via groups, permission
strings for HasPermission)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    tenant_id = models.UUIDField(null=True)
    permissions = models.JSONField(default=list, blank=True)
