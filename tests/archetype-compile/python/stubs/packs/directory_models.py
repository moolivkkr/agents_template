"""harness: the User model frameworks/django.md's query-optimization fragment assumes (a profile, groups,
a department) — the reader's model, not the one the doc's Models section shows."""
from django.contrib.auth.models import Group
from django.db import models


class User(models.Model):
    email = models.EmailField(unique=True)
    department = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    groups = models.ManyToManyField(Group, related_name="directory_users", blank=True)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    title = models.CharField(max_length=50, default="")
