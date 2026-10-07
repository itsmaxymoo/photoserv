from django.dispatch import receiver
from django.db import transaction
from media.signals import channel_photo_published, channel_photo_unpublished
from django.db.models.signals import post_save, post_delete
from media.models import Photo, PhotoMetadata, PhotoSize, Size, Album, PhotoInAlbum, Tag, PhotoTag
from integration.tasks import call_integration_plugin_signal, call_queue_global_integrations
from media.serializers import PhotoSerializer


def dispatch_photo_signal(channel_photo, signal_name):
    """
    Dispatch a channel photo event to integrations subscribed to that channel.
    
    Args:
        channel_photo: The ChannelPhoto instance that was published or unpublished
        signal_name: The plugin method to call ('on_photo_publish' or 'on_photo_unpublish')
    """
    photo_data = PhotoSerializer(channel_photo.photo).data
    channel_id = channel_photo.channel_id

    transaction.on_commit(
        lambda: call_integration_plugin_signal.delay(
            signal_name,
            data=photo_data,
            channel_id=channel_id,
        )
    )


@receiver(channel_photo_published)
def handle_photo_published(sender, instance, **kwargs):
    """Handle photo published event."""
    dispatch_photo_signal(instance, 'on_photo_publish')


@receiver(channel_photo_unpublished)
def handle_photo_unpublished(sender, instance, **kwargs):
    """Handle photo unpublished event."""
    dispatch_photo_signal(instance, 'on_photo_unpublish')


@receiver(channel_photo_published)
@receiver(channel_photo_unpublished)

@receiver(post_save, sender=Photo)
@receiver(post_save, sender=PhotoMetadata)
@receiver(post_save, sender=PhotoSize)
@receiver(post_save, sender=Size)
@receiver(post_save, sender=Album)
@receiver(post_save, sender=PhotoInAlbum)
@receiver(post_save, sender=Tag)
@receiver(post_save, sender=PhotoTag)

@receiver(post_delete, sender=Photo)
@receiver(post_delete, sender=PhotoMetadata)
@receiver(post_delete, sender=PhotoSize)
@receiver(post_delete, sender=Size)
@receiver(post_delete, sender=Album)
@receiver(post_delete, sender=PhotoInAlbum)
@receiver(post_delete, sender=Tag)
@receiver(post_delete, sender=PhotoTag)
def handle_global_integrations(*args, **kwargs):
    call_queue_global_integrations()
