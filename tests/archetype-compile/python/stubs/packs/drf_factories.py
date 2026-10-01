"""harness: the factory_boy factories frameworks/drf.md's tests use (UserFactory, WidgetFactory)."""
from uuid import uuid4

import factory
from factory.django import DjangoModelFactory

from apps.users.models import User
from apps.widgets.models import Widget


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    tenant_id = factory.LazyFunction(uuid4)
    password = factory.django.Password("pw-harness-1")


class WidgetFactory(DjangoModelFactory):
    class Meta:
        model = Widget

    tenant_id = factory.LazyFunction(uuid4)
    name = factory.Sequence(lambda n: f"widget {n}")
    created_by = 1
