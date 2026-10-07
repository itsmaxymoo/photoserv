from unittest import mock
from django.template import Context
from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError, transaction
from media import UI_THUMBNAIL_SMALL
from media import services
from media.models import *
from media.tables import ChannelPhotoTable
from datetime import timedelta


class ChannelTests(TestCase):
    def setUp(self):
        self.channel: Channel = Channel.objects.create(
            name = "B"
        )
        self.default_channel: Channel = Channel.objects.get(builtin=True)
        self.photo: Photo = Photo.objects.create(
            title="Test Photo",
            description="A test photo",
            raw_image="test.jpg",
            canonical_publish_date = timezone.now()
        )
        self.default_channel.add_photo(self.photo)

    def test_add_photo_unpublished_by_default(self):
        self.channel.add_photo(self.photo)
        self.assertFalse(self.photo.is_published(self.channel))
        self.assertEqual(self.channel.photos.all()[0].photo.canonical_publish_date, self.photo.channels.all()[0].publish_date)

    def test_channel_and_photo_are_unique_together(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChannelPhoto.objects.create(
                    channel=self.default_channel,
                    photo=self.photo,
                )

    def test_channel_photo_table_thumbnail_uses_photo_id(self):
        other_photo = Photo.objects.create(
            title="Other Photo",
            raw_image="other.jpg",
        )
        ChannelPhoto.objects.create(channel=self.channel, photo=self.photo)
        channel_photo = ChannelPhoto.objects.create(
            channel=self.channel,
            photo=other_photo,
        )

        table = ChannelPhotoTable([channel_photo])
        table.context = Context({"UI_THUMBNAIL_SMALL": UI_THUMBNAIL_SMALL})
        thumbnail = table.rows[0].get_cell("thumbnail")

        self.assertNotEqual(channel_photo.pk, other_photo.pk)
        self.assertIn(
            reverse(
                "photo-image",
                kwargs={"pk": other_photo.pk, "size": UI_THUMBNAIL_SMALL},
            ),
            thumbnail,
        )

    def test_no_publish_when_unhealthy(self):
        self.channel.add_photo(self.photo)

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_published.send") as mock_publish:
            channel_photo.update_published()

            self.assertFalse(channel_photo.published)
            mock_publish.assert_not_called()

    def test_photo_does_not_publish_until_all_sizes_are_generated(self):
        self.channel.add_photo(self.photo)
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")
        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_published.send") as mock_publish:
            channel_photo.update_published()

        self.assertFalse(channel_photo.published)
        mock_publish.assert_not_called()

    def test_publish_when_healthy(self):
        self.channel.add_photo(self.photo)

        # Add metadata
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")

        # Add all sizes
        for size in Size.objects.all():
            PhotoSize.objects.create(
                photo=self.photo,
                size=size,
                image=f"{size.slug}.jpg",
            )

        self.photo.refresh_from_db()

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_published.send") as mock_publish:
            channel_photo.update_published()
            channel_photo.save()

            self.assertTrue(channel_photo.published)
            mock_publish.assert_called_once()

    def test_publish_photos_service_updates_channel_photos(self):
        with mock.patch.object(ChannelPhoto, "update_published", return_value=True) as update_published:
            changed = services.publish_photos()

        self.assertEqual(changed, 1)
        update_published.assert_called_once_with()
    
    def broken_published_photo_not_revoked(self):
        PhotoMetadata.objects.all().delete()

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            channel_photo.update_published()
            channel_photo.save()

            self.assertTrue(channel_photo.published)
            mock_publish.assert_not_called()
    
    def move_publish_date_unpublished(self):
        channel_photo = self.channel.photos.first()
        channel_photo.publish_date = timezone.now() + timedelta(days=365)
        channel_photo.save()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            channel_photo.update_published()

            self.assertFalse(channel_photo.published)
            mock_publish.assert_called_once()

        channel_photo.publish_date = timezone.now() - timedelta(days=365)
        channel_photo.update_published()
        channel_photo.save()
    
    def delete_channel_unpublish(self):
        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            self.channel.delete()
            mock_publish.assert_called_once()
        
        self.assertFalse(ChannelPhoto.objects.filter(pk=self.channel.pk).exists())
    
    def delete_photo_unpublish(self):
        channel_photo = self.default_channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            self.photo.delete()
            mock_publish.assert_called_once()
        
        self.assertFalse(ChannelPhoto.objects.filter(pk=self.channel.pk).exists())


class ForkChannelTests(TestCase):
    def setUp(self):
        self.source = Channel.objects.create(
            name="Source channel",
            description="Source description",
            include_new_photos=False,
        )
        self.published_photo = Photo.objects.create(
            title="Published photo",
            raw_image="published.jpg",
        )
        self.future_photo = Photo.objects.create(
            title="Future photo",
            raw_image="future.jpg",
        )
        self.published_channel_photo = ChannelPhoto.objects.create(
            channel=self.source,
            photo=self.published_photo,
            publish_date=timezone.now() - timedelta(days=1),
            published=True,
        )
        self.future_channel_photo = ChannelPhoto.objects.create(
            channel=self.source,
            photo=self.future_photo,
            publish_date=timezone.now() + timedelta(days=1),
            published=False,
        )

    def test_fork_copies_independent_channel_photos_with_publication_state(self):
        fork = services.fork_channel(self.source, "Forked channel")

        source_photos = list(self.source.photos.order_by("photo_id"))
        forked_photos = list(fork.photos.order_by("photo_id"))

        self.assertEqual([item.photo_id for item in forked_photos], [item.photo_id for item in source_photos])
        self.assertEqual({item.pk for item in forked_photos}.intersection(item.pk for item in source_photos), set())
        self.assertEqual(fork.photos.count(), 2)
        self.assertEqual(self.source.photos.count(), 2)

        for source_channel_photo, forked_channel_photo in zip(source_photos, forked_photos):
            self.assertEqual(forked_channel_photo.publish_date, source_channel_photo.publish_date)
            self.assertEqual(forked_channel_photo.published, source_channel_photo.published)
            self.assertEqual(forked_channel_photo.channel, fork)
            self.assertEqual(source_channel_photo.channel, self.source)

    def test_fork_without_future_photos_copies_only_published_channel_photos(self):
        fork = services.fork_channel(
            self.source,
            "Published-only fork",
            include_future=False,
        )

        self.assertEqual(list(fork.photos.values_list("photo_id", flat=True)), [self.published_photo.pk])
        self.assertFalse(fork.photos.filter(photo=self.future_photo).exists())
        self.assertEqual(self.source.photos.count(), 2)

    def test_fork_does_not_dispatch_channel_photo_publish_signals(self):
        with (
            mock.patch("media.signals.channel_photo_published.send") as published_signal,
            mock.patch("media.signals.channel_photo_unpublished.send") as unpublished_signal,
        ):
            services.fork_channel(self.source, "Signal-free fork")

        published_signal.assert_not_called()
        unpublished_signal.assert_not_called()
