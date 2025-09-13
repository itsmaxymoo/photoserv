from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import *
from api_key.models import APIKey
import io
from PIL import Image


def create_test_image_file(filename="test.jpg"):
    """Create a simple in-memory JPEG file"""
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file, "JPEG")
    file.name = filename
    file.seek(0)
    return SimpleUploadedFile(file.name, file.read(), content_type="image/jpeg")


class APISerializerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # --- Create Sizes ---
        self.size_original = Size.objects.get(slug="original")
        self.size_medium = Size.objects.create(slug="medium", max_dimension=50, square_crop=False)

        # --- Create a Photo ---
        self.photo = Photo.objects.create(
            title="Test Photo",
            raw_image=create_test_image_file()
        )

        # Attach a PhotoSize for the original size
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size_original,
            image=create_test_image_file("original.jpg")
        )

        # --- Create Albums ---
        self.album1 = Album.objects.create(title="Album One", description="Test album 1")
        self.album2 = Album.objects.create(title="Album Two", description="Test album 2")
        self.photo.assign_albums([self.album1, self.album2])

        # --- Create Tags ---
        self.tag1 = Tag.objects.create(name="sunset")
        self.tag2 = Tag.objects.create(name="vacation")
        PhotoTag.objects.create(photo=self.photo, tag=self.tag1)
        PhotoTag.objects.create(photo=self.photo, tag=self.tag2)

        # --- Create API Key ---
        self.api_key = APIKey.create_key("public_rest_api test key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

    # --- Size Tests ---
    def test_sizes_exist(self):
        sizes = Size.objects.all()
        self.assertTrue(sizes.exists())
        self.assertIn(self.size_original, sizes)
        self.assertIn(self.size_medium, sizes)

    # --- Photo Tests ---
    def test_photos_exist(self):
        photos = Photo.objects.all()
        self.assertTrue(photos.exists())
        self.assertIn(self.photo, photos)

    # --- Album Tests ---
    def test_albums_exist(self):
        albums = Album.objects.all()
        self.assertTrue(albums.exists())
        self.assertIn(self.album1, albums)
        self.assertIn(self.album2, albums)

    # --- Tag Tests ---
    def test_tags_exist(self):
        tags = Tag.objects.all()
        self.assertTrue(tags.exists())
        self.assertIn(self.tag1, tags)
        self.assertIn(self.tag2, tags)
    
    # --- Authentication API test ---
    def test_public_api_authentication_required(self):
        url = f"/api/photos/{self.photo.uuid}/"
        response = APIClient().get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_public_api_authentication_correct(self):
        url = f"/api/photos/{self.photo.uuid}/"
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}-NOTHAHA")
        response = api.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    # --- Photo detail API test ---
    def test_photo_detail_returns_tag_and_album_summaries(self):
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        # Verify tags are included
        tag_uuids = [tag['uuid'] for tag in data['tags']]
        self.assertIn(str(self.tag1.uuid), tag_uuids)
        self.assertIn(str(self.tag2.uuid), tag_uuids)

        # Verify albums are included
        album_uuids = [album['uuid'] for album in data['albums']]
        self.assertIn(str(self.album1.uuid), album_uuids)
        self.assertIn(str(self.album2.uuid), album_uuids)

    # --- Album detail API test ---
    def test_album_detail_returns_ordered_photos(self):
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Album detail should include photos
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(self.photo.uuid), photo_uuids)

    # --- Tag detail API test ---
    def test_tag_detail_returns_related_photos(self):
        url = f"/api/tags/{self.tag1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify photos list includes our photo
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(self.photo.uuid), photo_uuids)


class APISizeDetailTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create API Key
        self.api_key = APIKey.create_key("size_test_key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

        # Create a test photo
        self.photo = Photo.objects.create(
            title="Test Photo for Sizes",
            raw_image=create_test_image_file()
        )

        # Original size for photo attachment
        self.size_original = Size.objects.get(slug="original")
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size_original,
            image=create_test_image_file("original.jpg")
        )

    def test_private_size_not_listed_or_accessible(self):
        # Create a private size
        private_size = Size.objects.create(
            slug="private_size",
            max_dimension=200,
            square_crop=False,
            public=False
        )
        PhotoSize.objects.create(photo=self.photo, size=private_size, image=create_test_image_file("private.jpg"))

        # 1. Ensure private size does not show up in /api/sizes
        response = self.client.get("/api/sizes/")
        self.assertEqual(response.status_code, 200)
        size_slugs = [s['slug'] for s in response.json()]
        self.assertNotIn(private_size.slug, size_slugs)

        # 2. Ensure accessing photo size returns 404
        url = f"/api/photos/{self.photo.uuid}/sizes/{private_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_size_listed_and_accessible(self):
        # Create a public size
        public_size = Size.objects.create(
            slug="public_size",
            max_dimension=300,
            square_crop=True,
            public=True
        )
        PhotoSize.objects.create(photo=self.photo, size=public_size, image=create_test_image_file("public.jpg"))

        # 1. Ensure public size shows up in /api/sizes
        response = self.client.get("/api/sizes/")
        self.assertEqual(response.status_code, 200)
        size_slugs = [s['slug'] for s in response.json()]
        self.assertIn(public_size.slug, size_slugs)

        # 2. Ensure accessing photo size works
        url = f"/api/photos/{self.photo.uuid}/sizes/{public_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
