from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.test import APIClient
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated

from django.utils import timezone
from datetime import timedelta

from .models import APIKey
from .authentication import APIKeyAuthentication


# ---- Virtual api view ----
class ProtectedView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = APIKey.objects.all()

    def get(self, request):
        return Response(
            {
                "detail": "Access granted",
                "username": request.user.username,
                "api_key": request.auth.name,
            }
        )


    def post(self, request):
        return Response(
            {
                "detail": "Access granted",
                "username": request.user.username,
                "api_key": request.auth.name,
            }
        )


urlpatterns = [
    path("api/", ProtectedView.as_view(), name="api"),
]


# ---- Tests ----
@override_settings(ROOT_URLCONF=__name__)
class APIKeyAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="api-key-user")
        self.raw_key = APIKey.create_key("test-key", user=self.user)

    def test_access_without_key_fails(self):
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_access_with_valid_key_succeeds(self):
        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "Access granted")
        self.assertEqual(response.json()["username"], self.user.username)
        self.assertEqual(response.json()["api_key"], "test-key")

    def test_access_with_expired_key_fails(self):
        # Expire the key
        key_obj = APIKey.objects.first()
        key_obj.expires_on = timezone.now() - timedelta(days=1)
        key_obj.save()

        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_access_with_malformed_header_fails(self):
        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION="NotBearer sometoken"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_access_with_wrong_key_fails(self):
        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION="Bearer notarealkey"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_access_with_extra_spaces_fails(self):
        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION="Bearer    " + self.raw_key
        )
        self.assertEqual(response.status_code, 401)

    def test_is_expired_property(self):
        key_obj = APIKey.objects.first()
        # Fresh key should not be expired
        self.assertFalse(key_obj.is_expired())

        # Expire manually
        key_obj.expires_on = timezone.now() - timedelta(days=1)
        self.assertTrue(key_obj.is_expired())

    def test_multiple_keys_validates_correctly(self):
        raw_key2 = APIKey.create_key("second-key", user=self.user)
        
        # First key still works
        response1 = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}"
        )
        self.assertEqual(response1.status_code, 200)

        # Second key works too
        response2 = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {raw_key2}"
        )
        self.assertEqual(response2.status_code, 200)

    def test_empty_authorization_header_fails(self):
        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=""
        )
        self.assertEqual(response.status_code, 401)


    def test_key_for_inactive_user_fails(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}",
        )

        self.assertEqual(response.status_code, 401)


@override_settings(ROOT_URLCONF=__name__)
class APIKeyModelPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="api-key-permission-user"
        )

    def test_post_requires_the_linked_users_add_permission(self):
        raw_key = APIKey.create_key("unprivileged-key", user=self.user)

        response = self.client.post(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {raw_key}",
        )

        self.assertEqual(response.status_code, 403)

    def test_post_uses_the_linked_users_model_permissions(self):
        permission = Permission.objects.get(
            content_type__app_label="api_key",
            codename="add_apikey",
        )
        self.user.user_permissions.add(permission)
        raw_key = APIKey.create_key("model-permission-key", user=self.user)

        response = self.client.post(
            "/api/",
            HTTP_AUTHORIZATION=f"Bearer {raw_key}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], self.user.username)
        self.assertEqual(response.json()["api_key"], "model-permission-key")
