from django.dispatch import receiver
from core.signals import photo_published, photo_unpublished
from django.db.models.signals import post_save, post_delete
from core.models import Photo, PhotoMetadata, PhotoSize, Size, Album, PhotoInAlbum, Tag, PhotoTag
from integration.tasks import call_queue_global_integrations, call_plugin_signal
from public_rest_api.serializers import PhotoSerializer


@receiver(photo_published)
def handle_photo_published(sender, instance, **kwargs):
    """Handle photo published event."""
    # Defer serialization until after the transaction commits
    # to ensure the photo has an ID and all related data is saved
    call_plugin_signal.delay('on_photo_publish', data=PhotoSerializer(instance).data)


@receiver(photo_unpublished)
def handle_photo_unpublished(sender, instance, **kwargs):
    """Handle photo unpublished event."""
    # Defer serialization until after the transaction commits
    # to ensure the photo has an ID and all related data is saved
    call_plugin_signal.delay('on_photo_unpublish', data=PhotoSerializer(instance).data)


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