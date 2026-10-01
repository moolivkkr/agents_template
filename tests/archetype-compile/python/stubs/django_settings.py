"""harness-only Django settings so the Channels modules can be imported and set up. REDIS_URL and
ALLOWED_ORIGINS come from the environment, as websocket-pattern-python.md's myapp/ modules expect."""
import json
import os

SECRET_KEY = "harness-only-not-a-secret"  # noqa: S105 — throwaway settings for an import check
INSTALLED_APPS = ["channels"]
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
DATABASES: dict[str, dict[str, str]] = {}
USE_TZ = True
REDIS_URL = os.environ["REDIS_URL"]
ALLOWED_ORIGINS = json.loads(os.environ["ALLOWED_ORIGINS"])
