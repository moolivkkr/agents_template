"""harness: the Django project around frameworks/drf.md's settings block (apps, database, middleware, the
custom user model). The doc's REST_FRAMEWORK / SIMPLE_JWT block follows this text in config/settings.py."""
SECRET_KEY = "harness-only-not-a-secret"  # noqa: S105 — throwaway settings for a test run
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",  # APIClient.force_authenticate(user=None) logs the test client out
    "rest_framework",
    "django_filters",
    "apps.users",
    "apps.widgets",
]
MIDDLEWARE = [
    "config.middleware.RequestIdMiddleware",  # every response carries X-Request-Id (DRF authenticates by JWT)
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
ROOT_URLCONF = "config.urls"
USE_TZ = True
LOGGING = {"version": 1, "disable_existing_loggers": False, "root": {"level": "CRITICAL"}}
