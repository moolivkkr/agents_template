"""harness-only Django settings so the Channels consumer module can be imported and set up."""
SECRET_KEY = "harness-only-not-a-secret"  # noqa: S105 — throwaway settings for an import check
INSTALLED_APPS = ["channels"]
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
DATABASES: dict[str, dict[str, str]] = {}
USE_TZ = True
