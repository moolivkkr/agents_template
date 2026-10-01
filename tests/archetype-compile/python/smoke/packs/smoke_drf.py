# frameworks/drf.md: the project starts (django.setup, system checks) and every module built from the doc
# imports without a warning from its own code. The behaviour runs in the post step under Django's test
# runner: the doc's APITestCase suite plus tests/test_drf_harness.py.
import importlib

import django

django.setup()

from django.core.management import call_command  # noqa: E402

call_command("check", fail_level="WARNING")
for mod in ("config.settings", "apps.core.exceptions", "apps.core.renderers", "apps.core.pagination",
            "apps.widgets.filters", "apps.widgets.serializers", "apps.widgets.permissions",
            "apps.widgets.services", "apps.widgets.views", "apps.users.serializers", "config.urls"):
    importlib.import_module(mod)
