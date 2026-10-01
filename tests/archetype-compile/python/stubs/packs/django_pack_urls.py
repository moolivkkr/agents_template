"""harness: URLconf for frameworks/django.md's ViewSet (the app's wiring, not in the doc)."""
from rest_framework.routers import DefaultRouter

from myapp.views import UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
urlpatterns = router.urls
