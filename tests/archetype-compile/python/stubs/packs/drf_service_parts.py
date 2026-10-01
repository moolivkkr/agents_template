from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from apps.core.exceptions import ConflictError
from apps.widgets.models import AuditLog, Widget

SENT: list[tuple[object, str, object]] = []


class NotificationService:  # harness: the app's notifier
    @staticmethod
    def send(tenant_id, event, obj):
        SENT.append((tenant_id, event, obj))


class _WidgetServiceParts:  # harness: the service methods frameworks/drf.md's ViewSet calls but doesn't show
    @staticmethod
    def update(instance, user_id, *, version, **data):
        with transaction.atomic():
            changed = Widget.objects.filter(pk=instance.pk, version=version, deleted_at__isnull=True).update(
                version=F("version") + 1, updated_at=timezone.now(), **data)
            if not changed:
                raise ConflictError()
            AuditLog.objects.create(action="widget.updated", entity_id=instance.id, actor_id=user_id)
        instance.refresh_from_db()
        return instance

    @staticmethod
    def soft_delete(instance, user_id):
        Widget.objects.filter(pk=instance.pk).update(deleted_at=timezone.now())

    @staticmethod
    def archive(widget, user_id):
        widget.status = "archived"
        widget.save(update_fields=["status", "updated_at"])
        return widget

    @staticmethod
    def get_stats(tenant_id):
        rows = Widget.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).values("status").annotate(
            n=Count("id"))
        return {r["status"]: r["n"] for r in rows}
