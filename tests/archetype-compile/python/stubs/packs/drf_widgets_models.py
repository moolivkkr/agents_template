"""harness: the models frameworks/drf.md's widget app uses (Widget with its category, soft delete and lock
version; the AuditLog the service and the signal write)."""
import uuid

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=50)


class Widget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=2000, blank=True, default="")
    status = models.CharField(max_length=20, default="active")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)


class AuditLog(models.Model):
    action = models.CharField(max_length=50)
    entity_id = models.UUIDField()
    actor_id = models.BigIntegerField()
    at = models.DateTimeField(auto_now_add=True)
