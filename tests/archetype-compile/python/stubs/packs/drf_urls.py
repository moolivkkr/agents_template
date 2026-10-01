"""harness: URLconf for frameworks/drf.md's project — the doc's widget router, simplejwt's token view (with
the doc's claims serializer), and two probes: a view that crashes (the 500 path) and one guarded by
HasPermission."""
from django.urls import include, path
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.widgets.permissions import HasPermission, IsAdminOrReadOnly


class Boom(APIView):
    def get(self, request):
        raise RuntimeError("secret internal detail")


class Archive(APIView):
    permission_classes = [IsAuthenticated, HasPermission("widgets.archive")]

    def post(self, request):
        return Response({"archived": True})


class Settings(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get(self, request):
        return Response({"theme": "dark"})

    def put(self, request):
        return Response({"theme": request.data["theme"]})


urlpatterns = [
    path("api/v1/", include("apps.widgets.views")),
    path("api/v1/auth/token/", TokenObtainPairView.as_view()),
    path("api/v1/boom/", Boom.as_view()),
    path("api/v1/archive-all/", Archive.as_view()),
    path("api/v1/settings/", Settings.as_view()),
]
