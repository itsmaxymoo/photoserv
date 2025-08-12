# photos/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Photo, PhotoSize, Size

@receiver(post_save, sender=Photo)
def create_original_photo_size(sender, instance, created, **kwargs):
    if created:
        try:
            original_size = Size.objects.get(slug="original")
        except Size.DoesNotExist:
            return
        PhotoSize.objects.get_or_create(
            photo=instance,
            size=original_size,
            defaults={'image': instance.raw_image}
        )
