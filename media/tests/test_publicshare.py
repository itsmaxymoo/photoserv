import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from media.models import Channel, ChannelPhoto, Photo, PhotoSize, PublicShare, Size
from media.tasks import consistency


TEST_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


@override_settings(CACHES=TEST_CACHES, CELERY_TASK_ALWAYS_EAGER=True)
class PublicShareModelTests(TestCase):
    def setUp(self):
        self.photo = Photo.objects.create(title="Shared photo", raw_image="raw.jpg")
        self.size = Size.objects.create(slug="shared", max_dimension=800)
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size,
            image="shared.jpg",
        )

    @override_settings(
        MEDIA_PUBLIC_SHARE_DEFAULT_EXPIRATION=7,
        MEDIA_PUBLIC_SHARE_DEFAULT_VIEWS=4,
    )
    def test_defaults_come_from_settings(self):
        before = timezone.now() + timedelta(days=7)
        share = PublicShare.objects.create(photo=self.photo, size=self.size)
        after = timezone.now() + timedelta(days=7)

        self.assertEqual(share.views_remaining, 4)
        self.assertGreaterEqual(share.expiration_date, before)
        self.assertLessEqual(share.expiration_date, after)

    @override_settings(MEDIA_PUBLIC_SHARE_MAX_EXPIRATION=3)
    def test_expiration_cannot_exceed_configured_maximum(self):
        with self.assertRaisesMessage(
            ValidationError,
            "MEDIA_PUBLIC_SHARE_MAX_EXPIRATION",
        ):
            PublicShare.objects.create(
                photo=self.photo,
                size=self.size,
                expiration_date=timezone.now() + timedelta(days=4),
            )

    def test_null_limits_create_a_permanent_unlimited_share(self):
        share = PublicShare.objects.create(
            photo=self.photo,
            size=self.size,
            expiration_date=None,
            views_remaining=None,
        )

        self.assertTrue(share.is_valid)


@override_settings(CACHES=TEST_CACHES, CELERY_TASK_ALWAYS_EAGER=True)
class PublicShareAPITests(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_root.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.photo = Photo.objects.create(title="API shared photo", raw_image="raw.jpg")
        self.size = Size.objects.create(slug="api-shared", max_dimension=800)
        self.channel = Channel.objects.create(name="Public share", builtin=True)
        ChannelPhoto.objects.create(
            channel=self.channel,
            photo=self.photo,
            published=True,
        )
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size,
            image=SimpleUploadedFile(
                "shared.jpg",
                b"public image bytes",
                content_type="image/jpeg",
            ),
        )

    def permission(self, action):
        content_type = ContentType.objects.get_for_model(PublicShare)
        return Permission.objects.get(
            content_type=content_type,
            codename=f"{action}_publicshare",
        )

    def client_with_permission(self, action):
        user = get_user_model().objects.create_user(username=f"share-{action}")
        user.user_permissions.add(self.permission(action))
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_anonymous_download_invokes_share_and_consumes_a_view(self):
        share = PublicShare.objects.create(
            photo=self.photo,
            size=self.size,
            views_remaining=1,
        )

        with patch.object(
            Photo,
            "get_size",
            autospec=True,
            return_value=self.photo_size,
        ) as get_size:
            response = APIClient().get(
                f"/api/public-shares/{share.uuid}/image/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), b"public image bytes")
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("shared.jpg", response["Content-Disposition"])
        self.assertEqual(get_size.call_count, 2)
        get_size.assert_called_with(share.photo, self.size.slug)
        share.refresh_from_db()
        self.assertEqual(share.views_remaining, 0)
        self.assertEqual(
            APIClient().get(
                f"/api/public-shares/{share.uuid}/image/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_expired_share_download_is_not_found(self):
        share = PublicShare.objects.create(photo=self.photo, size=self.size)
        PublicShare.objects.filter(pk=share.pk).update(
            expiration_date=timezone.now() - timedelta(seconds=1)
        )

        response = APIClient().get(
            f"/api/public-shares/{share.uuid}/image/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_crud_access_is_denied(self):
        share = PublicShare.objects.create(photo=self.photo, size=self.size)
        client = APIClient()

        for method, url in (
            (client.get, "/api/public-shares/"),
            (client.get, f"/api/public-shares/{share.uuid}/"),
            (client.delete, f"/api/public-shares/{share.uuid}/"),
        ):
            self.assertIn(
                method(url).status_code,
                {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
            )

        self.assertEqual(
            self.client_with_permission("view").get(
                f"/api/public-shares/{share.uuid}/"
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_crud_uses_public_share_model_permissions(self):
        created = self.client_with_permission("add").post(
            "/api/public-shares/",
            {"photo": str(self.photo.uuid), "size": str(self.size.uuid)},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        share = PublicShare.objects.get(uuid=created.data["uuid"])

        listed = self.client_with_permission("view").get(
            "/api/public-shares/"
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

        changed = self.client_with_permission("change").patch(
            f"/api/public-shares/{share.uuid}/",
            {"views_remaining": 5},
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)

        deleted = self.client_with_permission("delete").delete(
            f"/api/public-shares/{share.uuid}/"
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    @override_settings(MEDIA_PUBLIC_SHARE_MAX_EXPIRATION=2)
    def test_api_rejects_expiration_after_configured_maximum(self):
        response = self.client_with_permission("add").post(
            "/api/public-shares/",
            {
                "photo": str(self.photo.uuid),
                "size": str(self.size.uuid),
                "expiration_date": (
                    timezone.now() + timedelta(days=3)
                ).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expiration_date", response.data)


@override_settings(CACHES=TEST_CACHES, CELERY_TASK_ALWAYS_EAGER=True)
class PublicShareConsistencyTests(TestCase):
    def test_consistency_deletes_invalid_shares(self):
        photo = Photo.objects.create(title="Expired shared photo", raw_image="raw.jpg")
        size = Size.objects.create(slug="expired-shared", max_dimension=800)
        PhotoSize.objects.create(
            photo=photo,
            size=size,
            image="missing.jpg",
        )
        share = PublicShare.objects.create(photo=photo, size=size)
        PublicShare.objects.filter(pk=share.pk).update(views_remaining=0)

        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            consistency()

        self.assertFalse(PublicShare.objects.filter(pk=share.pk).exists())
