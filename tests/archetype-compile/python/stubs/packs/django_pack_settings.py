"""harness-only Django settings for frameworks/django.md's samples: SQLite in memory, DRF, the doc's app
(myapp) and a second app holding the fuller User model the query-optimization fragment assumes."""
SECRET_KEY = "harness-only-not-a-secret"  # noqa: S105 — throwaway settings for a test run
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "myapp",
    "directory",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "harness_urls"
USE_TZ = True
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "harness_pagination.NewestFirstCursorPagination",
    "UNAUTHENTICATED_USER": None,
}
