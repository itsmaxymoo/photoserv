import io
import tempfile

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api_key.models import APIKey
from media.models import (
    Album,
    Channel,
    ChannelPhoto,
    Photo,
    PhotoInAlbum,
    PhotoSize,
    PhotoTag,
    Size,
    Tag,
)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class MediaAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        key = APIKey.create_key("media api tests", write=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")

        self.photo = Photo.objects.create(title="API photo", raw_image="raw.jpg")
        self.size = Size.objects.create(
            slug="api-test-public",
            max_dimension=1000,
            public=True,
        )
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size,
            image="resized.jpg",
            height=10,
            width=20,
        )
        self.channel = Channel.objects.create(name="API channel", builtin=True)
        ChannelPhoto.objects.create(
            channel=self.channel,
            photo=self.photo,
            publish_date=self.photo.canonical_publish_date,
            published=True,
        )

    def assert_no_numeric_identity(self, value):
        if isinstance(value, dict):
            self.assertNotIn("id", value)
            self.assertNotIn("pk", value)
            for child in value.values():
                self.assert_no_numeric_identity(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_numeric_identity(child)

    def create_image_upload(self, filename="upload.jpg"):
        image_bytes = io.BytesIO()
        Image.new("RGB", (10, 10), color="blue").save(image_bytes, "JPEG")
        return SimpleUploadedFile(
            filename,
            image_bytes.getvalue(),
            content_type="image/jpeg",
        )

    def test_lists_are_paginated_and_page_size_is_capped(self):
        response = self.client.get("/api/photos/?page_size=10001")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 1)

    def test_photo_list_and_detail_always_include_sizes(self):
        list_response = self.client.get("/api/photos/")
        detail_response = self.client.get(f"/api/photos/{self.photo.uuid}/")

        self.assertEqual(len(list_response.data["results"][0]["sizes"]), 1)
        self.assertEqual(len(detail_response.data["sizes"]), 1)
        self.assertNotIn("image", detail_response.data["sizes"][0])
        self.assertNotIn("raw_image", detail_response.data)
        self.assertNotIn("image", detail_response.data)
        self.assert_no_numeric_identity(list_response.data)
        self.assert_no_numeric_identity(detail_response.data)

    def test_photo_create_accepts_binary_image_field(self):
        included_channel = Channel.objects.create(
            name="Auto-add channel",
            include_new_photos=True,
        )
        excluded_channel = Channel.objects.create(
            name="Manual channel",
            include_new_photos=False,
        )
        response = self.client.post(
            "/api/photos/",
            {"title": "Uploaded photo", "image": self.create_image_upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = Photo.objects.get(uuid=response.data["uuid"])
        self.assertTrue(photo.raw_image.name)
        self.assertNotIn("raw_image", response.data)
        self.assertNotIn("image", response.data)
        self.assertTrue(
            ChannelPhoto.objects.filter(
                photo=photo,
                channel=included_channel,
                publish_date=photo.canonical_publish_date,
            ).exists()
        )
        self.assertFalse(
            ChannelPhoto.objects.filter(
                photo=photo,
                channel=excluded_channel,
            ).exists()
        )

    def test_hidden_photo_create_does_not_add_channel_memberships(self):
        Channel.objects.create(name="Hidden auto-add", include_new_photos=True)

        response = self.client.post(
            "/api/photos/",
            {
                "title": "Hidden uploaded photo",
                "canonical_hidden": True,
                "image": self.create_image_upload("hidden-upload.jpg"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = Photo.objects.get(uuid=response.data["uuid"])
        self.assertFalse(ChannelPhoto.objects.filter(photo=photo).exists())

    def test_photo_detail_includes_channel_membership_header(self):
        response = self.client.get(f"/api/photos/{self.photo.uuid}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership = next(
            item
            for item in response.data["channels"]
            if item["channel"]["uuid"] == str(self.channel.uuid)
        )
        self.assertTrue(membership["published"])
        self.assertIn("publish_date", membership)

    def test_include_unpublished_controls_all_photo_get_responses(self):
        unpublished = Photo.objects.create(
            title="Unpublished photo",
            raw_image="unpublished.jpg",
        )
        ChannelPhoto.objects.create(
            channel=self.channel,
            photo=unpublished,
            published=False,
        )
        album = Album.objects.create(title="Visibility album")
        PhotoInAlbum.objects.create(album=album, photo=self.photo, order=1)
        PhotoInAlbum.objects.create(album=album, photo=unpublished, order=2)
        tag = Tag.objects.create(name="visibility")
        PhotoTag.objects.create(photo=self.photo, tag=tag)
        PhotoTag.objects.create(photo=unpublished, tag=tag)
        secondary_channel = Channel.objects.create(name="Visibility channel")
        ChannelPhoto.objects.create(channel=secondary_channel, photo=self.photo)
        ChannelPhoto.objects.create(channel=secondary_channel, photo=unpublished)

        photo_list = self.client.get("/api/photos/")
        all_photo_list = self.client.get(
            "/api/photos/?include_unpublished=true"
        )
        self.assertNotIn(
            str(unpublished.uuid),
            [item["uuid"] for item in photo_list.data["results"]],
        )
        self.assertIn(
            str(unpublished.uuid),
            [item["uuid"] for item in all_photo_list.data["results"]],
        )

        self.assertEqual(
            self.client.get(f"/api/photos/{unpublished.uuid}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(
                f"/api/photos/{unpublished.uuid}/?include_unpublished=true"
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/photos/{unpublished.uuid}/",
                {"title": "Still editable"},
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )

        for url in (
            f"/api/albums/{album.uuid}/",
            f"/api/tags/{tag.uuid}/",
            f"/api/channels/{secondary_channel.uuid}/",
        ):
            default_response = self.client.get(url)
            all_response = self.client.get(f"{url}?include_unpublished=true")
            default_photos = default_response.data["photos"]
            all_photos = all_response.data["photos"]
            if url.startswith("/api/channels/"):
                default_uuids = [item["photo"]["uuid"] for item in default_photos]
                all_uuids = [item["photo"]["uuid"] for item in all_photos]
            else:
                default_uuids = [item["uuid"] for item in default_photos]
                all_uuids = [item["uuid"] for item in all_photos]
            self.assertNotIn(str(unpublished.uuid), default_uuids)
            self.assertIn(str(unpublished.uuid), all_uuids)

    def test_channel_detail_includes_photos_with_sizes_and_header(self):
        response = self.client.get(f"/api/channels/{self.channel.uuid}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership = response.data["photos"][0]
        self.assertEqual(membership["photo"]["uuid"], str(self.photo.uuid))
        self.assertEqual(len(membership["photo"]["sizes"]), 1)
        self.assertTrue(membership["published"])

    def test_album_detail_always_includes_photos(self):
        album = Album.objects.create(title="API album")
        PhotoInAlbum.objects.create(album=album, photo=self.photo, order=1)

        response = self.client.get(f"/api/albums/{album.uuid}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["photos"][0]["uuid"], str(self.photo.uuid))
        self.assertEqual(len(response.data["photos"][0]["sizes"]), 1)

    def test_album_detail_can_include_descendant_photos(self):
        parent = Album.objects.create(title="Parent API album")
        child = Album.objects.create(title="Child API album", parent=parent)
        PhotoInAlbum.objects.create(album=child, photo=self.photo, order=1)

        normal = self.client.get(f"/api/albums/{parent.uuid}/")
        recursive = self.client.get(
            f"/api/albums/{parent.uuid}/?recursive=true"
        )

        self.assertEqual(normal.data["photos"], [])
        self.assertEqual(recursive.data["photos"][0]["uuid"], str(self.photo.uuid))

    def test_tag_detail_lists_photos(self):
        tag = Tag.objects.create(name="listed")
        PhotoTag.objects.create(photo=self.photo, tag=tag)

        self.assertEqual(self.client.get("/api/tags/").status_code, status.HTTP_200_OK)
        response = self.client.get(f"/api/tags/{tag.uuid}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["photos"][0]["uuid"], str(self.photo.uuid))
        self.assertEqual(len(response.data["photos"][0]["sizes"]), 1)

    def test_photo_relationship_endpoints_are_not_exposed(self):
        for relationship in ("tags", "albums", "channels"):
            url = f"/api/photos/{self.photo.uuid}/{relationship}/"
            self.assertEqual(
                self.client.post(url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )
            self.assertEqual(
                self.client.delete(url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )

    def test_album_and_channel_endpoints_add_one_photo(self):
        album = Album.objects.create(title="Relationship album")
        channel = Channel.objects.create(name="Relationship channel")

        album_response = self.client.post(
            f"/api/albums/{album.uuid}/photo/",
            {"photo": str(self.photo.uuid)},
            format="json",
        )
        channel_response = self.client.post(
            f"/api/channels/{channel.uuid}/photo/",
            {"photo": str(self.photo.uuid), "publish_date": None},
            format="json",
        )

        self.assertEqual(album_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(channel_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(album_response.data["uuid"], str(album.uuid))
        self.assertEqual(channel_response.data["uuid"], str(channel.uuid))
        self.assertIn(
            str(self.photo.uuid),
            [photo["uuid"] for photo in album_response.data["photos"]],
        )
        self.assertIn(
            str(self.photo.uuid),
            [item["photo"]["uuid"] for item in channel_response.data["photos"]],
        )
        self.assertTrue(
            PhotoInAlbum.objects.filter(album=album, photo=self.photo).exists()
        )
        self.assertTrue(
            ChannelPhoto.objects.filter(channel=channel, photo=self.photo).exists()
        )

    def test_channel_photo_requires_publish_date_and_null_uses_now(self):
        channel = Channel.objects.create(name="Scheduled channel")
        url = f"/api/channels/{channel.uuid}/photo/"

        missing = self.client.post(
            url,
            {"photo": str(self.photo.uuid)},
            format="json",
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            url,
            {"photo": str(self.photo.uuid), "publish_date": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        relationship = ChannelPhoto.objects.get(channel=channel, photo=self.photo)
        self.assertIsNotNone(relationship.publish_date)

    def test_relationship_deletes_accept_photo_query_parameter(self):
        album = Album.objects.create(title="Delete relationship album")
        channel = Channel.objects.create(name="Delete relationship channel")
        PhotoInAlbum.objects.create(album=album, photo=self.photo, order=1)
        ChannelPhoto.objects.create(channel=channel, photo=self.photo)

        self.assertEqual(
            self.client.delete(
                f"/api/albums/{album.uuid}/photo/?photo={self.photo.uuid}",
            ).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/channels/{channel.uuid}/photo/?photo={self.photo.uuid}",
            ).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            PhotoInAlbum.objects.filter(album=album, photo=self.photo).exists()
        )
        self.assertFalse(
            ChannelPhoto.objects.filter(channel=channel, photo=self.photo).exists()
        )

    def test_tag_delete_photo_parameter_is_optional(self):
        detached_tag = Tag.objects.create(name="detach only")
        deleted_tag = Tag.objects.create(name="delete entirely")
        PhotoTag.objects.create(photo=self.photo, tag=detached_tag)

        self.assertEqual(
            self.client.delete(
                f"/api/tags/{detached_tag.uuid}/?photo={self.photo.uuid}",
            ).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertTrue(Tag.objects.filter(uuid=detached_tag.uuid).exists())
        self.assertFalse(
            PhotoTag.objects.filter(photo=self.photo, tag=detached_tag).exists()
        )

        self.assertEqual(
            self.client.delete(f"/api/tags/{deleted_tag.uuid}/").status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(Tag.objects.filter(uuid=deleted_tag.uuid).exists())

    def test_photo_size_download_accepts_size_uuid_or_slug(self):
        with tempfile.TemporaryDirectory() as media_root, self.settings(
            MEDIA_ROOT=media_root
        ):
            self.photo_size.image.save(
                "download.jpg",
                self.create_image_upload("download.jpg"),
                save=True,
            )

            by_uuid = self.client.get(
                f"/api/photos/{self.photo.uuid}/sizes/{self.size.uuid}/"
            )
            self.assertEqual(by_uuid.status_code, status.HTTP_200_OK)
            self.assertTrue(b"".join(by_uuid.streaming_content))

            by_slug = self.client.get(
                f"/api/photos/{self.photo.uuid}/sizes/{self.size.slug}/"
            )
            self.assertEqual(by_slug.status_code, status.HTTP_200_OK)
            self.assertTrue(b"".join(by_slug.streaming_content))

    def test_unpublished_photo_size_download_requires_include_unpublished(self):
        unpublished = Photo.objects.create(
            title="Unpublished download",
            raw_image="unpublished-download.jpg",
        )
        with tempfile.TemporaryDirectory() as media_root, self.settings(
            MEDIA_ROOT=media_root
        ):
            photo_size = PhotoSize.objects.create(
                photo=unpublished,
                size=self.size,
                image=self.create_image_upload("unpublished-size.jpg"),
            )
            url = f"/api/photos/{unpublished.uuid}/sizes/{self.size.uuid}/"

            self.assertEqual(
                self.client.get(url).status_code,
                status.HTTP_404_NOT_FOUND,
            )
            response = self.client.get(f"{url}?include_unpublished=true")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(b"".join(response.streaming_content))
            photo_size.image.close()

    def test_private_photo_size_download_always_returns_not_found(self):
        private_size = Size.objects.create(
            slug="private-download",
            max_dimension=500,
            public=False,
        )
        with tempfile.TemporaryDirectory() as media_root, self.settings(
            MEDIA_ROOT=media_root
        ):
            photo_size = PhotoSize.objects.create(
                photo=self.photo,
                size=private_size,
                image=self.create_image_upload("private-size.jpg"),
            )

            for size_identifier in (private_size.uuid, private_size.slug):
                url = (
                    f"/api/photos/{self.photo.uuid}/sizes/{size_identifier}/"
                    "?include_unpublished=true"
                )
                self.assertEqual(
                    self.client.get(url).status_code,
                    status.HTTP_404_NOT_FOUND,
                )
            photo_size.image.close()

    def test_tag_post_accepts_photo_and_photos_together(self):
        second_photo = Photo.objects.create(title="Second photo", raw_image="two.jpg")
        response = self.client.post(
            "/api/tags/",
            {
                "name": "attached",
                "photo": str(self.photo.uuid),
                "photos": [str(second_photo.uuid)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PhotoTag.objects.filter(
                photo=self.photo,
                tag__uuid=response.data["uuid"],
            ).exists()
        )
        self.assertTrue(
            PhotoTag.objects.filter(
                photo=second_photo,
                tag__uuid=response.data["uuid"],
            ).exists()
        )

    def test_tag_put_only_accepts_name_and_patch_is_disabled(self):
        tag = Tag.objects.create(name="before")

        response = self.client.put(
            f"/api/tags/{tag.uuid}/",
            {"name": "after"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tag.refresh_from_db()
        self.assertEqual(tag.name, "after")

        invalid = self.client.put(
            f"/api/tags/{tag.uuid}/",
            {"name": "again", "photos": [str(self.photo.uuid)]},
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.patch(
                f"/api/tags/{tag.uuid}/",
                {"name": "patched"},
                format="json",
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_size_detail_get_is_disabled(self):
        self.assertEqual(
            self.client.get(f"/api/sizes/{self.size.uuid}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
