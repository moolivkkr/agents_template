"""harness-only Django settings for languages/python.md's Django blocks: SQLite in memory, a custom user with
a tenant, DRF + simplejwt (iss/aud required), the doc's tenant middleware after authentication."""
SECRET_KEY = "harness-only-not-a-secret"  # noqa: S105 — throwaway settings for a test run
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "accounts",
    "myapp",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "myapp.middleware.TenantMiddleware",  # the doc: after AuthenticationMiddleware
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
ROOT_URLCONF = "harness_urls"
USE_TZ = True
SIMPLE_JWT = {"SIGNING_KEY": "harness-only-signing-key-0123456789abcdef", "ISSUER": "harness", "AUDIENCE": "harness"}
