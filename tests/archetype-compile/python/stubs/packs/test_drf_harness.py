"""harness: requests through every frameworks/drf.md block the doc's own tests don't reach — cursor pages
and the limit bounds, the optimistic-locking update, delete/archive/stats, HasPermission, the JWT
settings (iss/aud required) with the custom claims, and the error handler's 401/404/405/409/500."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.widgets.models import AuditLog, Widget
from tests.factories import UserFactory, WidgetFactory


def _error(resp):
    body = resp.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) <= {"code", "message", "details", "request_id", "retryable"}, body
    return body["error"]


class HarnessDRFTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_cursor_pages_follow_next_cursor_without_gaps(self):
        made = [WidgetFactory(tenant_id=self.user.tenant_id) for _ in range(5)]
        seen, cursor = [], None
        while True:
            url = "/api/v1/widgets/?limit=2" + (f"&cursor={cursor}" if cursor else "")
            body = self.client.get(url).json()
            self.assertEqual(set(body), {"data", "meta"})
            seen += [w["id"] for w in body["data"]]
            page = body["meta"]["pagination"]
            self.assertEqual(page["limit"], 2)
            if not page["has_more"]:
                self.assertIsNone(page["next_cursor"])
                break
            cursor = page["next_cursor"]
        self.assertEqual(sorted(seen), sorted(str(w.id) for w in made))

    def test_limit_outside_bounds_is_400_never_clamped(self):
        for bad, code in (("0", "out_of_range"), ("101", "out_of_range"), ("-3", "out_of_range"), ("x", "invalid_type")):
            resp = self.client.get(f"/api/v1/widgets/?limit={bad}")
            self.assertEqual(resp.status_code, 400, (bad, resp.content))
            err = _error(resp)
            self.assertEqual(err["code"], "VALIDATION_FAILED")
            self.assertEqual(err["details"][0]["field"], "limit")
            self.assertEqual(err["details"][0]["code"], code)
        self.assertEqual(self.client.get("/api/v1/widgets/?limit=100").json()["meta"]["pagination"]["limit"], 100)

    def test_ordering_param_cannot_change_the_cursor_order(self):
        WidgetFactory(tenant_id=self.user.tenant_id, name="a")
        WidgetFactory(tenant_id=self.user.tenant_id, name="b")
        names = [w["name"] for w in self.client.get("/api/v1/widgets/?ordering=name").json()["data"]]
        self.assertEqual(names, ["b", "a"])  # newest first, as the paginator orders, not by name

    def test_update_with_version_and_conflict(self):
        w = WidgetFactory(tenant_id=self.user.tenant_id, name="old")
        resp = self.client.patch(f"/api/v1/widgets/{w.id}/", {"name": "new", "version": 1}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()["data"]
        self.assertEqual((data["id"], data["name"]), (str(w.id), "new"))  # the read shape, not the input
        resp = self.client.patch(f"/api/v1/widgets/{w.id}/", {"name": "x", "version": 1}, format="json")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(_error(resp)["code"], "CONFLICT")
        resp = self.client.patch(f"/api/v1/widgets/{w.id}/", {"name": "x"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(_error(resp)["details"], [{"field": "version", "code": "required",
                                                    "message": "This field is required."}])

    def test_create_answers_with_the_read_shape_and_audits(self):
        resp = self.client.post("/api/v1/widgets/", {"name": "W"}, format="json", HTTP_X_REQUEST_ID="rid-7")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(set(resp.json()["data"]), {"id", "name", "description", "status", "created_at", "updated_at"})
        self.assertEqual(resp.json()["meta"], {"request_id": "rid-7"})
        self.assertEqual(resp["X-Request-Id"], "rid-7")
        self.assertEqual(Widget.objects.get(name="W").tenant_id, self.user.tenant_id)
        self.assertEqual(AuditLog.objects.filter(action="widget.created").count(), 2)  # service + the AVOID signal
        dup = self.client.post("/api/v1/widgets/", {"name": "w"}, format="json")
        self.assertEqual(dup.status_code, 400)
        self.assertEqual(_error(dup)["details"][0], {"field": "name", "code": "already_exists",
                                                     "message": "This value is already in use."})

    def test_delete_archive_stats(self):
        w = WidgetFactory(tenant_id=self.user.tenant_id)
        self.assertEqual(self.client.post(f"/api/v1/widgets/{w.id}/archive/").json()["data"]["status"], "archived")
        self.assertEqual(self.client.get("/api/v1/widgets/stats/").json()["data"], {"archived": 1})
        self.assertEqual(self.client.delete(f"/api/v1/widgets/{w.id}/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/widgets/{w.id}/").status_code, 404)
        self.assertTrue(Widget.objects.filter(pk=w.pk).exists())  # soft delete

    def test_has_permission_is_instantiable_in_permission_classes(self):
        self.assertEqual(self.client.post("/api/v1/archive-all/").status_code, 403)
        self.user.permissions = ["widgets.archive"]
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.post("/api/v1/archive-all/").json()["data"], {"archived": True})

    def test_is_admin_or_read_only(self):
        self.assertEqual(self.client.get("/api/v1/settings/").json()["data"], {"theme": "dark"})
        self.assertEqual(self.client.put("/api/v1/settings/", {"theme": "x"}, format="json").status_code, 403)
        admin = UserFactory(tenant_id=self.user.tenant_id, is_staff=True)
        self.client.force_authenticate(user=admin)
        self.assertEqual(self.client.put("/api/v1/settings/", {"theme": "x"}, format="json").json()["data"],
                         {"theme": "x"})

    def test_errors_are_the_envelope(self):
        resp = self.client.put("/api/v1/widgets/stats/", {}, format="json")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(_error(resp)["code"], "MALFORMED_REQUEST")
        resp = self.client.get("/api/v1/boom/")
        self.assertEqual(resp.status_code, 500)
        err = _error(resp)
        self.assertEqual((err["code"], err["message"]), ("INTERNAL", "Something went wrong."))
        self.assertNotIn("secret internal detail", resp.content.decode())


class HarnessFieldCodeTests(APITestCase):
    """DRF's native ErrorDetail codes, produced by real serializers, reach the wire as the envelope's closed
    set (the doc's custom_exception_handler)."""

    def test_native_codes_map_onto_the_closed_set(self):
        from rest_framework import serializers
        from rest_framework.validators import UniqueValidator

        from apps.core.exceptions import custom_exception_handler

        WidgetFactory(name="taken")

        class Probe(serializers.Serializer):
            missing = serializers.CharField()                                   # required
            empty = serializers.CharField()                                     # blank
            nothing = serializers.CharField()                                   # null
            short = serializers.CharField(min_length=3)                         # min_length
            long = serializers.CharField(max_length=2)                          # max_length
            low = serializers.IntegerField(min_value=1)                         # min_value
            high = serializers.IntegerField(max_value=5)                        # max_value
            choice = serializers.ChoiceField(choices=["a", "b"])                # invalid_choice
            name = serializers.CharField(validators=[UniqueValidator(queryset=Widget.objects.all())])  # unique
            number = serializers.IntegerField()                                 # invalid (DRF's own)
            own = serializers.CharField()

            def validate_own(self, value):
                raise serializers.ValidationError("bad format", code="invalid_format")  # already in the set

        data = {"empty": "", "nothing": None, "short": "ab", "long": "abc", "low": 0, "high": 6, "choice": "z",
                "name": "taken", "number": "x", "own": "v"}
        probe = Probe(data=data)
        self.assertFalse(probe.is_valid())
        native = {f: [d.code for d in errs] for f, errs in probe.errors.items()}
        self.assertEqual(native, {"missing": ["required"], "empty": ["blank"], "nothing": ["null"],
                                  "short": ["min_length"], "long": ["max_length"], "low": ["min_value"],
                                  "high": ["max_value"], "choice": ["invalid_choice"], "name": ["unique"],
                                  "number": ["invalid"], "own": ["invalid_format"]})
        resp = custom_exception_handler(serializers.ValidationError(probe.errors), {"request": None})
        self.assertEqual(resp.status_code, 400)
        wire = {d["field"]: d["code"] for d in resp.data["error"]["details"]}
        self.assertEqual(wire, {"missing": "required", "empty": "required", "nothing": "required",
                                "short": "too_short", "long": "too_long", "low": "out_of_range",
                                "high": "out_of_range", "choice": "invalid_value", "name": "already_exists",
                                "number": "invalid_value", "own": "invalid_format"})
        allowed = {"required", "invalid_type", "invalid_format", "invalid_value", "out_of_range", "too_short",
                   "too_long", "unknown_field", "invalid_cursor", "already_exists"}
        self.assertLessEqual(set(wire.values()), allowed)
        for d in resp.data["error"]["details"]:
            self.assertTrue(d["message"].startswith("This "), d)  # the catalog message, never DRF's text


class HarnessJWTTests(APITestCase):
    def test_token_carries_claims_and_iss_aud_are_required(self):
        user = UserFactory(username="jwt-user")
        resp = self.client.post("/api/v1/auth/token/", {"username": "jwt-user", "password": "pw-harness-1"},
                                format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        access = resp.json()["data"]["access"]
        claims = jwt.decode(access, options={"verify_signature": False})
        self.assertEqual(claims["tenant_id"], str(user.tenant_id))
        self.assertEqual((claims["iss"], claims["aud"]), (os.environ["JWT_ISSUER"], os.environ["JWT_AUDIENCE"]))
        ok = self.client.get("/api/v1/widgets/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(ok.status_code, 200, ok.content)

        now = datetime.now(timezone.utc)
        base = {"token_type": "access", "user_id": str(user.pk), "jti": uuid4().hex, "iat": now,
                "exp": now + timedelta(minutes=5)}
        key = os.environ["JWT_SIGNING_KEY"]
        for name, payload in (
            ("no aud", {**base, "iss": os.environ["JWT_ISSUER"]}),
            ("no iss", {**base, "aud": os.environ["JWT_AUDIENCE"]}),
            ("other service", {**base, "iss": os.environ["JWT_ISSUER"], "aud": "another-service"}),
        ):
            token = jwt.encode(payload, key, algorithm="HS256")
            resp = self.client.get("/api/v1/widgets/", HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED, name)
            self.assertEqual(_error(resp)["code"], "UNAUTHENTICATED", name)
