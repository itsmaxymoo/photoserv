from django.dispatch import receiver
from core.signals import photo_published, photo_unpublished
from django.db.models.signals import post_save, post_delete
from core.models import Photo, PhotoMetadata, PhotoSize, Size, Album, PhotoInAlbum, Tag, PhotoTag
from integration.tasks import call_queue_web_requests


@receiver(photo_published)
@receiver(photo_unpublished)

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
def handle_web_requests(*args, **kwargs):
    call_queue_web_requests()