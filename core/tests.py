from unittest import mock
from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import *
from .views import TagUpdateView
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.apps import apps


class PhotoModelTests(TestCase):
    def setUp(self):
        self.photo = Photo.objects.create(
            title="Test Photo",
            description="A test photo",
            raw_image="test.jpg",
        )

    def test_str_returns_title(self):
        self.assertEqual(str(self.photo), "Test Photo")

    def test_get_absolute_url(self):
        url = self.photo.get_absolute_url()
        self.assertIn(str(self.photo.pk), url)

    @mock.patch("core.tasks.generate_sizes_for_photo.delay_on_commit")
    @mock.patch("core.tasks.generate_photo_metadata.delay_on_commit")
    def test_save_triggers_tasks_on_create(self, mock_metadata, mock_sizes):
        p = Photo(title="Another", raw_image="raw.jpg")
        p.save()


        self.assertTrue(mock_sizes.called)
        self.assertTrue(mock_metadata.called)

    @mock.patch("core.tasks.delete_files.delay_on_commit")
    def test_delete_triggers_delete_files(self, mock_delete):
        self.photo.delete()
        self.assertTrue(mock_delete.called)

    def test_assign_albums_adds_and_removes(self):
        album1 = Album.objects.create(title="Album1", description="d")
        album2 = Album.objects.create(title="Album2", description="d")

        # assign album1
        self.photo.assign_albums([album1])
        self.assertTrue(PhotoInAlbum.objects.filter(photo=self.photo, album=album1).exists())

        # replace with album2
        self.photo.assign_albums([album2])
        self.assertFalse(PhotoInAlbum.objects.filter(photo=self.photo, album=album1).exists())
        self.assertTrue(PhotoInAlbum.objects.filter(photo=self.photo, album=album2).exists())
    
    def test_photo_health(self):
        # Initially, photo.health.* is false
        self.assertFalse(self.photo.health.metadata)
        self.assertFalse(self.photo.health.all_sizes)

        # Add metadata
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.health.metadata)
        self.assertFalse(self.photo.health.all_sizes)

        # Add sizes
        for size in Size.objects.all():
            PhotoSize.objects.create(photo=self.photo, size=size, image=f"{size.slug}.jpg")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.health.metadata)
        self.assertTrue(self.photo.health.all_sizes)


class PhotoSlugTests(TestCase):
    def test_photo_created_without_slug(self):
        # Create a photo without specifying a slug
        photo = Photo.objects.create(title="Photo Without Slug", raw_image="image.jpg")
        self.assertIsNotNone(photo.slug)
        self.assertTrue(photo.slug)

    def test_photo_can_be_updated(self):
        # Create and update a photo
        photo = Photo.objects.create(title="Initial Title", raw_image="image.jpg")
        photo.title = "Updated Title"
        photo.save()
        self.assertEqual(photo.title, "Updated Title")

    def test_photo_created_with_specific_slug(self):
        # Create a photo with a specific slug
        photo = Photo.objects.create(title="Photo With Slug", raw_image="image.jpg", slug="custom-slug")
        self.assertEqual(photo.slug, "custom-slug")

    def test_duplicate_slug_raises_validation_error(self):
        # Create a photo with a specific slug
        Photo.objects.create(title="First Photo", raw_image="image1.jpg", slug="duplicate-slug")
        
        # Attempt to create another photo with the same slug
        with self.assertRaises(ValidationError):
            photo = Photo(title="Second Photo", raw_image="image2.jpg", slug="duplicate-slug")
            photo.full_clean()  # Trigger validation


class PhotoMetadataTests(TestCase):
    def test_str_includes_photo(self):
        photo = Photo.objects.create(title="MetaPhoto", raw_image="raw.jpg")
        metadata = PhotoMetadata.objects.create(photo=photo, camera_make="Canon")
        self.assertIn("MetaPhoto", str(metadata))


class TagTests(TestCase):
    def setUp(self):
        self.tag = Tag.objects.create(name="nature")

    def test_str_returns_name(self):
        self.assertEqual(str(self.tag), "nature")

    def test_get_absolute_url(self):
        url = self.tag.get_absolute_url()
        self.assertIn(str(self.tag.pk), url)

    def test_clean_rejects_invalid_characters(self):
        t = Tag(name="bad;tag")
        with self.assertRaises(ValidationError):
            t.clean()

    def test_name_is_normalized_on_save(self):
        t = Tag.objects.create(name="  Nature  ")
        self.assertEqual(t.name, "nature")

    def test_merging_tags_moves_photo_tags(self):
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        t1 = Tag.objects.create(name="tree")
        t2 = Tag.objects.create(name="forest")
        PhotoTag.objects.create(photo=photo, tag=t1)

        # Rename t1 -> "forest", should merge into t2
        t1.name = "forest"
        merged = t1.save()
        self.assertEqual(PhotoTag.objects.filter(photo=photo, tag=t2).count(), 1)
        self.assertFalse(Tag.objects.filter(pk=t1.pk).exists())


class PhotoTagTests(TestCase):
    def test_str_returns_tag_name(self):
        photo = Photo.objects.create(title="T", raw_image="r.jpg")
        tag = Tag.objects.create(name="taggy")
        pt = PhotoTag.objects.create(photo=photo, tag=tag)
        self.assertEqual(str(pt), "taggy")

    def test_unique_constraint(self):
        photo = Photo.objects.create(title="T", raw_image="r.jpg")
        tag = Tag.objects.create(name="uniq")
        PhotoTag.objects.create(photo=photo, tag=tag)
        with self.assertRaises(Exception):
            PhotoTag.objects.create(photo=photo, tag=tag)
    
    def test_renaming_tag2_to_tag1_then_get_url_points_to_tag_list(self):
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        tag1 = Tag.objects.create(name="tag1")
        tag2 = Tag.objects.create(name="tag2")

        PhotoTag.objects.create(photo=photo, tag=tag1)
        PhotoTag.objects.create(photo=photo, tag=tag2)

        # Rename tag2 to tag1 — triggers merge (tag2 will be deleted)
        tag2.name = "tag1"
        tag2.save()

        # After merge, tag2 should be gone
        with self.assertRaises(ObjectDoesNotExist):
            Tag.objects.get(pk=tag2.pk)

        # Simulate the view's get_success_url() behavior
        # If the tag was merged and deleted, we should be redirected to tag-list
        view = TagUpdateView()
        view.object = tag2  # mimic what the view would have before deletion
        url = view.get_success_url()

        expected = reverse("tag-list")
        self.assertEqual(url, expected)


class AlbumTests(TestCase):
    def setUp(self):
        self.album = Album.objects.create(title="Holiday", description="Trip")

    def test_str_returns_title(self):
        self.assertEqual(str(self.album), "Holiday")

    def test_get_absolute_url(self):
        url = self.album.get_absolute_url()
        self.assertIn(str(self.album.pk), url)

    def test_get_ordered_photos_manual_order(self):
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=1)

        self.album.sort_method = Album.DefaultSortMethod.MANUAL
        ordered = list(self.album.get_ordered_photos())
        self.assertEqual(ordered[0], photo2)
    
    def test_album_parents(self):
        parent = Album.objects.create(title="Parent", description="Parent album")
        child = Album.objects.create(title="Child", description="Child album", parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

        # Test cyclic relationship prevention
        with self.assertRaises(ValidationError):
            parent.parent = child
            parent.full_clean()


class AlbumSlugTests(TestCase):
    def test_album_created_without_slug(self):
        # Create an album without specifying a slug
        album = Album.objects.create(title="Album Without Slug", description="A test album")
        self.assertIsNotNone(album.slug)
        self.assertTrue(album.slug)

    def test_album_can_be_updated(self):
        # Create and update an album
        album = Album.objects.create(title="Initial Title", description="A test album")
        album.title = "Updated Title"
        album.save()
        self.assertEqual(album.title, "Updated Title")

    def test_album_created_with_specific_slug(self):
        # Create an album with a specific slug
        album = Album.objects.create(title="Album With Slug", description="A test album", slug="custom-slug")
        self.assertEqual(album.slug, "custom-slug")

    def test_duplicate_slug_raises_validation_error(self):
        # Create an album with a specific slug
        Album.objects.create(title="First Album", description="A test album", slug="duplicate-slug")
        
        # Attempt to create another album with the same slug
        with self.assertRaises(ValidationError):
            album = Album(title="Second Album", description="Another test album", slug="duplicate-slug")
            album.full_clean()  # Trigger validation


class PhotoInAlbumTests(TestCase):
    def test_str_shows_album_and_photo(self):
        album = Album.objects.create(title="A", description="d")
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        pia = PhotoInAlbum.objects.create(album=album, photo=photo, order=1)
        self.assertIn("A -> P", str(pia))

    def test_assign_albums_reorders_and_replaces(self):
        album = Album.objects.create(title="My Album", description="desc")

        # initial photos
        p1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        p2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        p3 = Photo.objects.create(title="P3", raw_image="3.jpg")

        # First assignment: add all three to the album
        for p in (p1, p2, p3):
            p.assign_albums([album])
        self.assertEqual(PhotoInAlbum.objects.filter(album=album).count(), 3)

        # New photo
        p4 = Photo.objects.create(title="P4", raw_image="4.jpg")

        # Remove p2 explicitly
        p2.assign_albums([])

        # Ensure p1, p3, p4 are assigned
        for p in (p1, p3, p4):
            p.assign_albums([album])

        # Desired new order
        new_order = [p3, p1, p4]

        # Reorder explicitly
        PhotoInAlbum.objects.filter(album=album, photo=p3).update(order=1)
        PhotoInAlbum.objects.filter(album=album, photo=p1).update(order=2)
        PhotoInAlbum.objects.filter(album=album, photo=p4).update(order=3)

        qs = PhotoInAlbum.objects.filter(album=album).order_by("order")

        # Ensure count is 3
        self.assertEqual(qs.count(), 3)

        # Ensure correct set of photos in album
        self.assertEqual(set(qs.values_list("photo", flat=True)), {p1.id, p3.id, p4.id})

        # Ensure order matches [p3, p1, p4]
        expected = [p.id for p in new_order]
        actual = list(qs.values_list("photo", flat=True))
        self.assertEqual(expected, actual)

        # Ensure no gaps or duplicates in order
        orders = list(qs.values_list("order", flat=True))
        self.assertEqual(orders, list(range(1, len(new_order) + 1)))


class SizeTests(TestCase):
    def setUp(self):
        self.size = Size.objects.create(slug="medium", max_dimension=800, can_edit=True)

    def test_str_representation(self):
        self.assertEqual(str(self.size), "medium (800px)")

    def test_cannot_delete_builtin(self):
        builtin = Size.objects.create(slug="builtin", max_dimension=100, builtin=True, can_edit=False)
        with self.assertRaises(ValidationError):
            builtin.delete()

    @mock.patch("core.tasks.generate_photo_sizes_for_size.delay_on_commit")
    def test_save_triggers_task(self, mock_generate):
        self.size.save()
        self.assertTrue(mock_generate.called)


class PhotoSizeTests(TestCase):
    def test_str_representation(self):
        photo = Photo.objects.create(title="Photo", raw_image="r.jpg")
        size = Size.objects.create(slug="small", max_dimension=400)
        ps = PhotoSize.objects.create(photo=photo, size=size, image="resized.jpg")
        self.assertIn("Photo - small", str(ps))

    def test_unique_constraint(self):
        photo = Photo.objects.create(title="Photo", raw_image="r.jpg")
        size = Size.objects.create(slug="small", max_dimension=400)
        PhotoSize.objects.create(photo=photo, size=size, image="resized.jpg")
        with self.assertRaises(Exception):
            PhotoSize.objects.create(photo=photo, size=size, image="resized2.jpg")


class CommonEntityTests(TestCase):
    def test_created_at_and_updated_at(self):
        album = Album.objects.create(title="Album", description="desc")
        self.assertIsNotNone(album.created_at)
        self.assertIsNotNone(album.updated_at)

        old_updated_at = album.updated_at
        album.title = "New Title"
        album.save()
        self.assertGreater(album.updated_at, old_updated_at)
    
    def test_uuid_field_exists(self):
        photo_meta = PhotoMetadata.objects.create(photo=Photo.objects.create(title="P", raw_image="r.jpg"))
        self.assertIsNotNone(photo_meta.uuid)


class TestMigrations(TestCase):

    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass


class TestMigration0003(TestMigrations):
    migrate_from = "0002_album_parent_photo_hidden"
    migrate_to = "0003_core_entity_common_base"

    def setUpBeforeMigration(self, apps):
        # Use old apps registry to create multiple pre-migration Size objects
        SizeOld = apps.get_model("core", "Size")

        self.sizes = []
        for i in range(5):
            size = SizeOld.objects.create(
                slug=f"size-{i}",
                max_dimension=100 * (i + 1),
                can_edit=True,
            )
            self.sizes.append(size)

    def test_size_uuids_populated_and_unique_after_migration(self):
        # Use post-migration apps registry
        SizeNew = self.apps.get_model("core", "Size")

        uuids = set()
        for old_size in self.sizes:
            size_after = SizeNew.objects.get(pk=old_size.pk)
            
            # Assert UUID exists
            self.assertTrue(hasattr(size_after, "uuid"))
            self.assertIsNotNone(size_after.uuid)
            
            # Assert UUID is unique
            self.assertNotIn(size_after.uuid, uuids)
            uuids.add(size_after.uuid)

        # Extra check: all UUIDs are unique
        self.assertEqual(len(uuids), len(self.sizes))